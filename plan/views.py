import asyncio
import logging
import re
from datetime import date, datetime, timedelta
from csv import writer
from pathlib import Path
from shutil import make_archive, rmtree 
from xml.etree.cElementTree import XML
from zipfile import ZipFile
from zoneinfo import ZoneInfo
from striprtf.striprtf import rtf_to_text
from django.db.models import F, Q
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.http import (
    FileResponse,
    HttpResponse, 
    HttpResponseRedirect, 
    HttpResponseForbidden
)
from django.shortcuts import get_object_or_404, render
from django.views.generic import ListView, CreateView, UpdateView
from django.views.generic.edit import DeletionMixin
from django.urls import reverse
from .forms import (
    AuthForm,
    NewPatientForm,
    UploadFileForm,
    MultiUploadFileForm
)
from .models import Files, Patients


# Create your views here.
logger = logging.getLogger('django.server.file') # 'django.server.file'
directory = Files.docs_directory

@login_required
def download(request, filename: str) -> FileResponse: 
    """Return a file to the client side."""
    return FileResponse(open(directory+filename, 'rb'))

async def slice_load(request, filename: str, semaphore: int) -> FileResponse: 
    """Return a DICOM slice.
    
    *Template. Not for use.
    """
    async with semaphore:
        await asyncio.sleep(0.5) # RadiAnt issues (DON'T CHANGE!)
        return FileResponse(
            open('plan/dicom/'+filename, 'rb'), as_attachment=True
        )

async def dicom(
    request, ae_title: str, patient_id: int
) -> FileResponse | HttpResponseForbidden:
    """Return DICOM slices to the viewer.
    
    *Template. Not for use. Tested with Orthanc only. Awaiting the
    PACS interface information.
    """
    if Files.objects.filter(keys=ae_title).exists():
        data = Files.objects.filter(pid=patient_id)
        slices = [f for f in data]
        semaphore = asyncio.Semaphore(5)
        tasks = [slice_load(None, s, semaphore) for s in slices]
        await asyncio.gather(*tasks)
    else:
        return HttpResponseForbidden()

class AuthView(LoginView):
    authentication_form = AuthForm
    template_name = 'plan/login.html'
    next_page = '/main/'
    
    def get_context_data(self, **kwargs) -> dict: 
        if settings.DEBUG:
            kwargs['debug'] = 'ВКЛЮЧЁН РЕЖИМ ОТЛАДКИ!!!'
        if 'Mozilla/4.0' in self.request.headers['User-Agent']:
            kwargs['old_browser'] = True
        return super().get_context_data(**kwargs)
    
    def form_valid(self, form) -> HttpResponse:
        self.request.session.set_expiry(3600)
        return super().form_valid(form)

class ExitView(LoginRequiredMixin, LogoutView):
    template_name = 'plan/logout.html'
    next_page = '/'

class MainView(LoginRequiredMixin, ListView):
    template_name = 'plan/main.html'
    queryset = Patients.objects.order_by(F('hosp_date').asc(nulls_first=True))
    
    def get_context_data(self, **kwargs) -> dict:
        kwargs['calendar'] = self.calendar_data()
        if 'Mozilla/4.0' in self.request.headers['User-Agent']:
            kwargs['old_browser'] = True
        return super().get_context_data(**kwargs)
    
    def calendar_data(self) -> list:
        """Return five weeks calendar data for the main.html template."""
        now = datetime.now()
        target_day = now - timedelta(days=7)
        while target_day.isoweekday() != 1:
            target_day -= timedelta(days=1)
        months = [
            'Января', 
            'Февраля', 
            'Марта', 
            'Апреля', 
            'Мая', 
            'Июня', 
            'Июля', 
            'Августа', 
            'Сентября', 
            'Октября', 
            'Ноября', 
            'Декабря'
        ]
        weekdays = [
            'Понедельник', 
            'Вторник', 
            'Среда', 
            'Четверг', 
            'Пятница', 
            'Суббота', 
            'Воскресенье'
        ]
        five_weeks = []
        one_week = []
        for i in range(35):
            day = target_day.date().day
            month = months[target_day.date().month-1]
            year = target_day.date().year
            weekday = weekdays[target_day.date().weekday()]
            past = 'id_past'
            if target_day == now:
                past = 'id_today'
            elif target_day > now:
                past = 'id_future'
            day_dict = {
                'date': f'{day} {month} {year}',
                'weekday': weekday,
                'past': past,
                'hosp': self.queryset.filter(hosp_date=target_day.date()),
                'oper': self.queryset.filter(oper_date=target_day.date())
            }
            one_week.append(day_dict)
            if (i+1)%7 == 0:
                five_weeks.append(one_week)
                one_week = []
            target_day += timedelta(days=1)
        return five_weeks

@login_required
def csv_response(request) -> HttpResponse:
    """Returns all database data as a csv table."""
    response = HttpResponse(headers={
        'Content-Type': 'text/csv; charset=cp1251',
        'Content-Disposition': 'attachment; filename="plan.csv"',
    })
    to_csv = writer(response)
    to_csv.writerow([
        'Дата госпитализации', 'Дата операции', 'Врач', 'Пациент', 
        'Номер карты', 'Телефон', 'Диагноз', 'МКБ', 'Код ВМП', 
        'Тип', 'Заметки'
    ])
    patients = Patients.objects.all().values_list(
        'hosp_date', 'oper_date', 'physician', 'name', 
        'medical_card', 'phone', 'diagnosis', 'icd10', 'htmc_code', 
        'equipment', 'notes'
    )
    for patient in patients:
        to_csv.writerow(patient)
    return response

@login_required
def week_list(request) -> FileResponse | HttpResponse:
    """Return a list of scheduled surgeries for the next week."""
    try:
        files = Path.cwd()/'plan'/'src'/'files'
        old = files/'week.docx'
        old.unlink(missing_ok=True)
        template = files/'template.docx'
        copy = files/'copy.docx'
        copy.write_bytes(template.read_bytes())
        temp = files/'temp'
        rmtree(temp, ignore_errors=True)
        temp.mkdir()
        with ZipFile(copy, 'r') as z:
            z.extractall(temp)
        copy.unlink()
        with open(temp/'word'/'document.xml', 'r', encoding='utf8') as f:
            new = f.read()
            next_monday = date.today()
            # matching with the current monday is correctly
            while next_monday.isoweekday() != 1:
                next_monday += timedelta(days=1)
            next_sunday = next_monday + timedelta(days=6)
            n_m = next_monday.strftime('%d.%m.%Y')
            n_s = next_sunday.strftime('%d.%m.%Y')
            new = new.replace(
                '<w:t>дата</w:t>', 
                f'<w:t>Неделя с {n_m} по {n_s}</w:t>'
            )
            queryset = Patients.objects.filter(
                oper_date__range=(next_monday, next_sunday)
            ).values_list(
                'name', 'medical_card', 'diagnosis', 'quota', 'htmc_code'
            )
            mod_queryset = []
            for query in queryset:
                mod_queryset.append(list(query))
                i = mod_queryset[-1]
                i[0] = i[0] + ', №' + i[1]
                i[3] = i[3] + ' ' + i[4]
                i.pop(1)
                i.pop()
            for query in mod_queryset:
                for i in query:
                    new = new.replace('<w:t>т</w:t>', f'<w:t>{i}</w:t>', 1)
            new = new.replace('<w:t>т</w:t>', '<w:t></w:t>')
        with open(temp/'word'/'document.xml', 'w', encoding='utf8') as f:
            f.write(new)
        make_archive(copy, 'zip', temp)
        rmtree(temp, ignore_errors=True)
        week = files/'copy.docx.zip'
        week.rename(Path(week.parent, 'week.docx'))
        return FileResponse(
            open(files/'week.docx', 'rb'), as_attachment=True
        )
    except Exception as err:
        logger.error(err, exc_info=True)
        return HttpResponse('Произошла ошибка. Данные записаны в лог-файл.')

class NewPatientView(LoginRequiredMixin, CreateView):
    form_class = NewPatientForm
    template_name = 'plan/new.html'
    success_url = '/main/'
    
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.remove_files()
        self.remove_entries()
    
    def get_initial(self) -> dict:
        self.initial['alteration_user'] = self.request.user.username
        return super().get_initial()
    
    def get_context_data(self, upload_form=UploadFileForm(), **kwargs) -> dict:
        kwargs['upload_form'] = upload_form
        if 'Mozilla/4.0' in self.request.headers['User-Agent']:
            kwargs['old_browser'] = True
        return super().get_context_data(**kwargs)
    
    def post(self, request, *args, **kwargs) -> HttpResponse:
        if 'pat_obj' in request.POST:
            self.object = None
            return super().post(request, *args, **kwargs)
        elif 'file_obj' in request.POST:
            form = UploadFileForm(request.POST, request.FILES)
            if form.is_valid():
                file_instance = Files(doc=form.cleaned_data['file'])
                file_instance.save()
                inits = {'alteration_user': self.request.user.username}
                try:
                    if file_instance.doc.path.endswith('.rtf'):
                        plain_text = self.read_rtf(file_instance)
                    elif file_instance.doc.path.endswith('.docx'):
                        plain_text = self.read_docx(file_instance)
                    else:
                        raise Exception (
                            'Not supported extension', 
                            'Check the form validator'
                        )
                    inits.update(self.search_inits(plain_text))
                    inits.setdefault('foreign_key', file_instance)
                    inits.setdefault('plain_text', plain_text)
                    self.object = file_instance
                except Exception as err:
                    logger.error(err, exc_info=True)
                    form.add_error(
                        'file', f'Ошибка обработки файла: {type(err)=}'
                    )
                    file_instance.delete()
                    self.object = None
                    unbound = NewPatientForm(initial={
                        'alteration_user': self.request.user.username
                    })
                    return self.render_to_response(
                        self.get_context_data(upload_form=form, form = unbound)
                    )
                autocomplete = NewPatientForm(inits)
                return self.render_to_response(
                    self.get_context_data(form=autocomplete)
                )
            else:
                self.object = None
                return self.render_to_response(
                    self.get_context_data(upload_form=form)
                )
        elif 'del_file' in request.POST:
            file = get_object_or_404(Files, pk=request.POST['del_file'])
            file.delete()
            return HttpResponseRedirect(reverse('plan:new'))
        return super().post(request, *args, **kwargs)
    
    def read_rtf(self, file_object: Files) -> str:
        """Return .rtf file content as a plain text."""
        a = 'àáâãäå¸æçèéêëìíîïðñòóôõö÷øùúûüýþÿÀÁÂÃÄÅ¨ÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞß¹'
        b = 'абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ№'
        translator = str.maketrans({k:v for k, v in zip(a, b)})
        with open(file_object.doc.name, 'r') as f:
            rtf = f.read()
            broken_text = rtf_to_text(rtf)
        return broken_text.translate(translator)
    
    def read_docx(self, file_object: Files) -> str:
        """Return .docx file content as a plain text."""
        PARA = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'
        TEXT = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'
        with ZipFile(file_object.doc.name, 'r') as z:
            xml = z.read('word/document.xml')
        tree = XML(xml)
        all_text = ''
        for p in tree.iter(PARA):
            paragraph = ''
            for t in p.iter(TEXT):
                paragraph += t.text
            all_text += f'{paragraph}\n'
        return all_text
    
    def search_inits(self, text: str) -> dict:
        """Return initial values for the NewPatientForm() fields."""
        regex_dict = {
            'physician': r'нейрохирург:\s*([а-яА-ЯёЁ]*)\s*',
            'name': r'Пациент:\s*(.+)?Контактный',
            'medical_card': r'условиях №:\s*(.*)?',
            'phone': r'номер:\s*(.+)?',
            'diagnosis': r'Диагноз:\s*(.+)?',
            'icd10': r'\[(.+)?]',
            'htmc_code': r'направленного на\s*[а-яА-ЯёЁa-zA-Z,\-\s*]*(.*)',
            'quota': r'направленного на\s*([а-яА-ЯёЁa-zA-Z,\-\s*]*)\d*',
        }
        inits_dict = {'equipment': 'Стандарт'}
        for k, v in regex_dict.items():
            regex = re.compile(v)
            try:
                r_str = regex.search(text).group(1).strip()
                if k == 'name':
                    inits_dict.setdefault(k, r_str.title())
                elif k == 'quota':
                    r_str = r_str[0].capitalize() + r_str[1:]
                    inits_dict.setdefault(k, r_str)
                else:
                    inits_dict.setdefault(k, r_str)
            except:
                inits_dict.setdefault(k, None)
        return inits_dict
    
    def remove_files(self) -> None:
        """Removes old, unrelated files."""
        week_ago = datetime.now(ZoneInfo(settings.TIME_ZONE)) - timedelta(7)
        for_delete = Files.objects.exclude(
            patients__in=Patients.objects.filter(foreign_key__isnull=False)
        ).exclude(add_date__gte=week_ago)
        for i in for_delete:
            try:
                i.delete() # Remove entry+file by the model method
            except Exception as err:
                logger.error(err, exc_info=True)
                continue
    
    def remove_entries(self) -> None:
        """Removes older than target_day entries.""" 
        target_day = datetime.now() - timedelta(days=7)
        while target_day.isoweekday() != 1:
            target_day -= timedelta(days=1)
        for_delete = Patients.objects.filter(
            Q(hosp_date__lt=target_day) & Q(oper_date__lt=target_day)
        )
        for_delete.delete()

class UpdatePatientView(LoginRequiredMixin, UpdateView, DeletionMixin):
    model = Patients
    form_class = NewPatientForm
    template_name = 'plan/update.html'
    success_url = '/main/'
    
    def get_initial(self) -> dict:
        self.initial['alteration_user'] = self.request.user.username
        self.initial['timestamp'] = str(self.object.alteration_date)
        return super().get_initial()
    
    def get_context_data(self, **kwargs) -> dict:
        if 'Mozilla/4.0' in self.request.headers['User-Agent']:
            kwargs['old_browser'] = True
        return super().get_context_data(**kwargs)
    
    def post(self, request, *args, **kwargs) -> HttpResponse:
        if 'pat_obj' in request.POST:
            self.object = self.get_object()
            t1 = request.POST.get('timestamp')
            t2 = str(self.object.alteration_date)
            if t1 != t2:
                from_db=self.object.__dict__
                from_db['foreign_key'] = self.object.foreign_key
                from_db['previous_user'] = self.object.alteration_user
                from_db['alteration_user'] = self.request.user.username
                from_db['timestamp'] = str(self.object.alteration_date)
                autocomplete = NewPatientForm(from_db)
                backup = request.POST.dict()
                return self.render_to_response(
                    self.get_context_data(form=autocomplete, b=backup)
                )
            return super().post(request, *args, **kwargs)
        elif 'delete_obj' in request.POST:
            return self.delete(request, *args, **kwargs)
        return super().post(request, *args, **kwargs)

@login_required
def test(request):
    to_test = {
        'get_items': request.GET.items(),
        'get_expiry_age': request.session.get_expiry_age(),
        'multiple_file_form': MultiUploadFileForm(),
    }
    return render(request, 'plan/test.html', to_test)
