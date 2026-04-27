from django.db import models
from django.utils import timezone
from django.conf import settings
from subscription.models import Plan

class Payments(models.Model):
    STATUS = (
        ('pending','Pending'),
        ('paid','Paid'),
        ('failed','Failed'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan,on_delete=models.CASCADE)
    status = models.CharField(max_length=20,choices=STATUS,default='pending')
    tnxid = models.CharField(max_length=200,unique=True,blank=True, null=True)
    invoice = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user} - {self.plan.name} - {self.status} - {self.plan.price}"