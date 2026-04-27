from django.db import models
from django.conf import settings
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.core.exceptions import ValidationError
import uuid
# Create your models here.


class Plan(models.Model):
    PLAN = [
        ("free", "Free"),
        ("pro", "Pro"),
        ("vip", "Vip"),
    ]
    DURATION = [
        ("month", "Monthly"),
        ("anual","Annual"),
        ("permanent", "Permanent"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=20, choices=PLAN,unique=True)
    data = models.JSONField(default=list)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duration = models.CharField(max_length=20, choices=DURATION,default="permanent")
    
    
    def __str__(self):
        return f"{self.get_name_display()} ({self.get_duration_display()})"




class Subscriptions(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='subscriptions', on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
    start = models.DateTimeField(blank=True, null=True)
    end = models.DateTimeField(blank=True, null=True)
    active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.start:
            self.start = timezone.now()

        plan_obj = self.plan

        if plan_obj:
            if plan_obj.duration == 'month':
                self.end = self.start + relativedelta(months=1)
            elif plan_obj.duration == 'anual':
                self.end = self.start + relativedelta(years=1)
            elif plan_obj.duration == 'permanent':
                self.end = None
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} - {self.plan.name}"

