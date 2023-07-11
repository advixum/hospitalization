from pathlib import Path
from django.db import models
from django.db.models.functions import datetime


# Create your models here.
class Files(models.Model):
    docs_directory = 'plan/src/'
    doc = models.FileField(upload_to=docs_directory)
    add_date = models.DateTimeField(auto_now_add=True)
    """
    # Awaiting the PACS interface information.
    dicom_directory = 'plan/dicom/'
    pid = models.PositiveBigIntegerField() # ManyToManyField ???
    dicom = models.FileField(upload_to=dicom_directory)
    keys = models.CharField(max_length=16)
    """
    def delete(self):
        """Remove a file when the entry is deleted."""
        super().delete()
        Path(self.doc.name).unlink()
    
    def __str__(self):
        return Path(self.doc.name).name

class Patients(models.Model):
    foreign_key = models.ForeignKey(Files, on_delete=models.CASCADE, null=True)
    plain_text = models.TextField(blank=True)
    confirmation = models.BooleanField('Статус проверки', default=False)
    physician = models.CharField('Врач', max_length=200)
    name = models.CharField('Пациент', max_length=200)
    medical_card = models.CharField('Номер карты', max_length=7, blank=True)
    phone = models.CharField('Телефон', max_length=18, blank=True)
    hosp_date = models.DateField('Госпитализация', null=True, blank=True)
    oper_date = models.DateField('Операция', null=True, blank=True)
    diagnosis = models.TextField('Диагноз', blank=True)
    icd10 = models.CharField('МКБ', max_length=6, blank=True)
    htmc_code = models.CharField('Код ВМП', max_length=50, blank=True)
    quota = models.TextField('Квота', blank=True)
    equipment_types = models.TextChoices('Типы', 'Стандарт Нейромонитор AWAKE')
    equipment = models.CharField(
        'Тип', 
        max_length=15,
        choices=equipment_types.choices, 
        default='Стандарт'
    )
    notes = models.TextField('Заметки', blank=True)
    alteration_user = models.CharField(max_length=16, default='Unauthorized')
    alteration_date = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name.partition(' ')[0]
