from django import template

from logistics.document_numbers import display_document_number

register = template.Library()


@register.filter
def doc_number(document, document_type):
    return display_document_number(document, document_type)
