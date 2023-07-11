from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from django.contrib import auth
from django.contrib.auth.models import AnonymousUser, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.urls import reverse
from . import views
from .forms import NewPatientForm, UploadFileForm
from .models import Files, Patients



# Create your tests here.
"""
Основной целью данного тестирования является закрепление
усвоенных знаний на практике, а не исчерпывающий охват всех 
возможных тестовых случаев.
"""
class NotAuthenticatedUserTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.entry = Patients.objects.create(
            physician='physician', name='patient'
        )

    def test_not_authenticated_user_on_login_page(self):
        """
        The request succeeded for AnonymousUser().
        """
        request = self.factory.get('', HTTP_USER_AGENT='Mozilla/5.0')
        request.user = AnonymousUser()
        response = views.AuthView.as_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_not_authenticated_user_on_logout_page(self):
        """
        Redirect logout-to-login page for AnonymousUser().
        """
        request = self.factory.get('/logout/', HTTP_USER_AGENT='Mozilla/5.0')
        request.user = AnonymousUser()
        response = views.ExitView.as_view()(request)
        self.assertEqual(response.status_code, 302)

    def test_not_authenticated_user_on_main_page(self):
        """
        Redirect main-to-login page for AnonymousUser().
        """
        request = self.factory.get('/main/', HTTP_USER_AGENT='Mozilla/5.0')
        request.user = AnonymousUser()
        response = views.MainView.as_view()(request)
        self.assertEqual(response.status_code, 302)

    def test_not_authenticated_user_on_new_patient_page(self):
        """
        Redirect new-to-login page for AnonymousUser().
        """
        request = self.factory.get('/new/', HTTP_USER_AGENT='Mozilla/5.0')
        request.user = AnonymousUser()
        response = views.NewPatientView.as_view()(request)
        self.assertEqual(response.status_code, 302)

    def test_not_authenticated_user_on_update_page(self):
        """
        Redirect update-to-login page for AnonymousUser().
        """
        request = self.factory.get(
            reverse('plan:update', kwargs={'pk': self.entry.id}), 
            HTTP_USER_AGENT='Mozilla/5.0'
        )
        request.user = AnonymousUser()
        response = views.UpdatePatientView.as_view()(request)
        self.assertEqual(response.status_code, 302)

    def test_not_authenticated_user_on_table_page(self):
        """
        Redirect table-to-login page for AnonymousUser().
        """
        request = self.factory.get('/table/')
        request.user = AnonymousUser()
        response = views.csv_response(request)
        self.assertEqual(response.status_code, 302)

    def test_not_authenticated_user_on_week_page(self):
        """
        Redirect week-to-login page for AnonymousUser().
        """
        request = self.factory.get('/week/')
        request.user = AnonymousUser()
        response = views.week_list(request)
        self.assertEqual(response.status_code, 302)

    def test_not_authenticated_user_on_download_page(self):
        """
        Redirect download-to-login page for AnonymousUser().
        """
        request = self.factory.get(views.directory)
        request.user = AnonymousUser()
        response = views.download(request, 'some_file.rtf')
        self.assertEqual(response.status_code, 302)

class OldBrowserContextTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='test', password='top_secret'
        )
        self.entry = Patients.objects.create(
            physician='physician', name='patient'
        )

    def test_login_page_context_for_old_browser(self):
        """
        The login page context contains the old_browser key as True.
        """
        request = self.factory.get('/', HTTP_USER_AGENT='Mozilla/4.0')
        request.user = self.user
        view = views.AuthView()
        view.setup(request)
        context = view.get_context_data()
        self.assertIn('old_browser', context)
        self.assertTrue(context['old_browser'])

    def test_main_page_context_for_old_browser(self):
        """
        The main page context contains the old_browser key as True.
        """
        request = self.factory.get('/main/', HTTP_USER_AGENT='Mozilla/4.0')
        request.user = self.user
        view = views.MainView()
        view.setup(request)
        view.object_list = view.get_queryset()
        context = view.get_context_data()
        self.assertIn('old_browser', context)
        self.assertTrue(context['old_browser'])

    def test_new_patient_page_context_for_old_browser(self):
        """
        The new patient page context contains the old_browser key as
        True.
        """
        request = self.factory.get('/new/', HTTP_USER_AGENT='Mozilla/4.0')
        request.user = self.user
        view = views.NewPatientView()
        view.setup(request)
        view.object = None
        context = view.get_context_data()
        self.assertIn('old_browser', context)
        self.assertTrue(context['old_browser'])

    def test_update_page_context_for_old_browser(self):
        """
        The update page context contains the old_browser key as True.
        """
        request = self.factory.get(
            reverse('plan:update', kwargs={'pk': self.entry.id}),
            HTTP_USER_AGENT='Mozilla/4.0'
        )
        request.user = self.user
        view = views.UpdatePatientView()
        view.setup(request)
        view.object = self.entry#Patients.objects.create(physician='test1', name='test1')
        context = view.get_context_data()
        self.assertIn('old_browser', context)
        self.assertTrue(context['old_browser'])

class DownloadViewTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='test', password='top_secret'
        )

    def test_file_was_loaded(self):
        """
        The resulting and source files must match.
        """
        request = self.factory.get(views.directory)
        request.user = self.user
        response = views.download(request, 'files/template.docx')
        with BytesIO(response.getvalue()) as f:
            b_file = f.read()
        src = Path.cwd()/'plan'/'src'/'files'/'template.docx'
        b_src = src.read_bytes()
        self.assertEqual(b_file, b_src)

class AuthViewTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='test', password='top_secret'
        )

    def test_form_was_hidden(self):
        """
        AuthForm is hidden if the user is authenticated.
        """
        request = self.factory.get('/', HTTP_USER_AGENT='Mozilla/5.0')
        request.user = self.user
        response = views.AuthView.as_view()(request)
        self.assertContains(response, 'Перейти на главную')
        self.assertNotContains(response, '<form method="post">')

    def test_session_duration_less_or_equal_3600(self):
        """
        The session duration should not exceed 1 hour.
        """
        self.client.post(
            '/',
            data={'username': 'test', 'password': 'top_secret'}, 
            HTTP_USER_AGENT='Mozilla/5.0'
        )
        session = self.client.session
        self.assertLessEqual(session.get_expiry_age(), 3600)

class ExitViewTests(TestCase):

    def setUp(self):
        User.objects.create_user(username='test', password='top_secret')

    def test_user_was_logged_out(self):
        """
        The user is logged out if he visits the logout page.
        """
        self.client.login(username='test', password='top_secret')
        self.client.get('/logout/', HTTP_USER_AGENT='Mozilla/5.0')
        user = auth.get_user(self.client)
        self.assertFalse(user.is_authenticated)

class MainViewTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='test', password='top_secret'
        )
        self.entry_with_date = Patients.objects.create(
            physician='physician', 
            name='patient', 
            hosp_date=date.today(),
            oper_date=date.today()
        )
        self.entry_no_date = Patients.objects.create(
            physician='physician', name='patient'
        )

    def test_entry_with_date_was_showed(self):
        """
        Patient records are displayed in the calendar.
        """
        request = self.factory.get('/', HTTP_USER_AGENT='Mozilla/5.0')
        request.user = self.user
        response = views.MainView.as_view()(request)
        self.assertContains(
            response, 
            f'<a id="id_based" href="/{self.entry_with_date.id}/">patient</a>'
        )
        self.assertContains(
            response, 
            f'<a id="id_red" href="/{self.entry_with_date.id}/">patient</a>'
        )

    def test_no_date_entry_was_showed(self):
        """
        Patients without a hospitalization date are displayed in the 
        general list.
        """
        request = self.factory.get('/', HTTP_USER_AGENT='Mozilla/5.0')
        request.user = self.user
        response = views.MainView.as_view()(request)
        self.assertContains(
            response, 
            f'<a href="/{self.entry_no_date.id}/">Дата не указана</a>'
        )

class UpdatePatientViewTests(TestCase):

    def setUp(self):
        User.objects.create_user(username='test', password='top_secret')
        self.entry = Patients.objects.create(
            physician='test_upd', name='old_data'
        )

    def test_avoiding_race_conditions(self):
        """
        The user cannot update the data if someone else has updated it.
        """
        self.client.login(username='test', password='top_secret')
        request = self.client.get(
            reverse('plan:update', kwargs={'pk': self.entry.id}), 
            HTTP_USER_AGENT='Mozilla/5.0'
        )
        form = {
            'name': 'conflict_data', 
            'physician': 'test_upd',
            'pat_obj': '', 
            'timestamp': request.context[-1]['widget']['value']
        }
        another_user_update_entry = Patients.objects.get(pk=self.entry.id)
        another_user_update_entry.name = 'new_data'
        another_user_update_entry.save()
        self.client.post(
            reverse('plan:update', kwargs={'pk': self.entry.id}), 
            data=form, 
            HTTP_USER_AGENT='Mozilla/5.0'
        )
        self.assertNotEqual(
            Patients.objects.get(pk=self.entry.id).name, 'conflict_data'
        )

class FilesModelTests(TestCase):

    def test_file_was_unlinked(self):
        """
        File must be removed when the entry is deleted.
        """
        template = Path.cwd()/'plan'/'static'/'files'/'Шаблон.rtf'
        filename = str(uuid4()) + '.rtf'
        src = Path.cwd()/'plan'/'src'/filename
        with open(template, 'rb') as f:
            file_instance = Files(doc=SimpleUploadedFile(filename, f.read()))
            file_instance.save()
        Files.objects.get(pk=1).delete()
        self.assertFalse(src.exists())

class NewPatientFormTests(TestCase):

    def test_hosp_date_was_less_than_target_day(self):
        """
        hosp_date cannot be less than target_day.
        """
        target_day = date.today() - timedelta(days=7)
        while target_day.isoweekday() != 1:
            target_day -= timedelta(days=1)
        less_than_target_day = target_day - timedelta(days=1)
        form_data = {'hosp_date': less_than_target_day}
        form = NewPatientForm(data=form_data)
        self.assertEqual(
            form.errors['hosp_date'], 
            [f'Дата должна быть равна или позднее {target_day}.']
        )

    def test_oper_date_was_less_than_target_day(self):
        """
        oper_date cannot be less than target_day.
        """
        target_day = date.today() - timedelta(days=7)
        while target_day.isoweekday() != 1:
            target_day -= timedelta(days=1)
        less_than_target_day = target_day - timedelta(days=1)
        form_data = {'oper_date': less_than_target_day}
        form = NewPatientForm(data=form_data)
        self.assertEqual(
            form.errors['oper_date'], 
            [f'Дата должна быть равна или позднее {target_day}.']
        )

class UploadFileFormTests(TestCase):

    def test_rtf_file_was_loaded(self):
        """
        UploadFileForm can receive a .rtf file.
        """
        with open(Path.cwd()/'plan'/'static'/'files'/'Шаблон.rtf', 'rb') as f:
            form_data = {'file': SimpleUploadedFile(f.name, f.read())}
            form = UploadFileForm(files=form_data)
            self.assertTrue(form.is_valid())

    def test_docx_file_was_loaded(self):
        """
        UploadFileForm can receive a .docx file.
        """
        with open(Path.cwd()/'plan'/'static'/'files'/'Шаблон.docx', 'rb') as f:
            form_data = {'file': SimpleUploadedFile(f.name, f.read())}
            form = UploadFileForm(files=form_data)
            self.assertTrue(form.is_valid())

    def test_another_files_was_not_loaded(self):
        """
        UploadFileForm cannot get files other than .rtf and .docx.
        """
        with open(Path.cwd()/'plan'/'static'/'files'/'htmc.pdf', 'rb') as f:
            form_data = {'file': SimpleUploadedFile(f.name, f.read())}
            form = UploadFileForm(files=form_data)
            self.assertFalse(form.is_valid())