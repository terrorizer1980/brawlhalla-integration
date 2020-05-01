from tortoise import Model
from tortoise.fields import BigIntField, IntField


class BrawlhallaUser(Model):
    discord_id = BigIntField(pk=True, generated=False)
    brawlhalla_id = IntField()