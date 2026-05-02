from django.db import models
import uuid


class FAQ(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.CharField(max_length=200,verbose_name="Question")
    answer = models.TextField(blank=True, null=True,verbose_name="Answer")
    is_active = models.BooleanField(default=True,verbose_name="Is Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.question




class Support(models.Model):
    email = models.EmailField(max_length=255,verbose_name="Email")
    phone = models.CharField(max_length=200,verbose_name="Phone No")

    def __str__(self):
        return self.phone
