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




class PrivacyPolicy(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Privacy Policy"




class PrivacyPolicyContent(models.Model):
    policy = models.ForeignKey(PrivacyPolicy, on_delete=models.CASCADE, related_name='contents')
    order = models.IntegerField(verbose_name="Order", default=0,unique=True)
    title = models.CharField(max_length=200,verbose_name="Title")
    content = models.TextField(blank=True, null=True,verbose_name="Content")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Content for {self.policy}"




class TermsAndConditions(models.Model):
    effective_date = models.DateField(verbose_name="Effective Date")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Terms And Conditions ({self.effective_date})"




class TermsAndConditionsContent(models.Model):
    terms = models.ForeignKey(TermsAndConditions, on_delete=models.CASCADE, related_name='contents')
    order = models.IntegerField(verbose_name="Order", default=0,unique=True)
    content = models.TextField(blank=True, null=True,verbose_name="Content")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Content for {self.terms}"