"""Reusable staff signature profiles and signed document audit records."""

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from ._legacy import CustomUser


class SignatureProfile(models.Model):
    """Uploaded signature image and title for a system user."""

    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="signature_profile"
    )
    signature_image = models.FileField(upload_to="signatures/", blank=True, null=True)
    title = models.CharField(max_length=120, default="Authorized Signatory")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__username"]
        verbose_name = "Signature Profile"
        verbose_name_plural = "Signature Profiles"

    def __str__(self):
        return f"{self.display_name} signature"

    @property
    def display_name(self):
        full_name = self.user.get_full_name().strip()
        return full_name or self.user.username

    @property
    def can_sign(self):
        return bool(self.is_active and self.signature_image)


class DocumentSignature(models.Model):
    """Audit record showing which user signed a business document and when."""

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    signed_by = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="document_signatures"
    )
    signature_profile = models.ForeignKey(
        SignatureProfile, on_delete=models.PROTECT, related_name="document_signatures"
    )
    signer_name = models.CharField(max_length=150)
    signer_title = models.CharField(max_length=120)
    note = models.CharField(max_length=255, blank=True)
    signed_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-signed_at", "-created_at"]
        verbose_name = "Document Signature"
        verbose_name_plural = "Document Signatures"
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id"],
                name="one_signature_per_business_document",
            )
        ]

    def __str__(self):
        return f"{self.content_object} signed by {self.signer_name}"
