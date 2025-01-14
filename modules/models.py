import re
from tortoise import fields, Tortoise, run_async
from tortoise.models import Model

class Link(Model):
    link = fields.CharField(max_length=255, unique=True)
    status = fields.CharField(max_length=50, null=True)

    def __str__(self):
        return self.link

    class Meta:
        ordering = ['link']
