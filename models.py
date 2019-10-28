from datetime import datetime
from config import db, ma
from marshmallow import fields

"""
SQLAlchemy models
"""

class CpsuFiles(db.Model):
    __tablename__ = 'cpsu_files'
    filename = db.Column(db.String(50), primary_key=True, nullable=False)
    read_time = db.Column(db.DateTime, default=datetime.utcnow)

class Channel(db.Model):
    __tablename__ = 'channel'
    channel_id = db.Column(db.Integer, primary_key=True)
    channel = db.Column(db.String(32), nullable=False)
    breakid = db.relationship(
        'BreakId',
        backref='channel',
        cascade='all, delete, delete-orphan',
        single_parent=True,
        lazy=True
        )


# TODO: make instime UTC?
class BreakId(db.Model):
    __tablename__ = 'breakid'
    breakid_id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.channel_id'))
    breakid = db.Column(db.Integer)
    casu_adid = db.Column(db.Integer)
    instime = db.Column(db.DateTime)
    cpsu = db.relationship(
        'Cpsu',
        backref='breakid',
        cascade='all,delete,delete-orphan',
        single_parent=True
        # ,order_by'desc(Cpsu.time?)'
        )


class Cpsu(db.Model):
    __tablename__ = 'cpsu'
    cpsu_id = db.Column(db.Integer, primary_key=True)
    breakid_id = db.Column(db.Integer, db.ForeignKey('breakid.breakid_id'))
    duration = db.Column(db.Float)
    flag_mask = db.Column(db.SmallInteger)
    full_play_flag = db.Column(db.SmallInteger)
    profile = db.Column(db.Integer)
    sdv_result = db.Column(db.SmallInteger)
    stb_mac = db.Column(db.String(32))


"""
Marshmallow schemas derived from above SQLAlchemy models
"""

class CpsuFileSchema(ma.ModelSchema):
    class Meta:
        model = CpsuFiles
        sqla_session = db.session


class ChannelSchema(ma.ModelSchema):
    class Meta:
        model = Channel
        sqla_session = db.session

    breakid = fields.Nested('ChannelBreakIdSchema', default=[], many=True)


class BreakIdSchema(ma.ModelSchema):
    class Meta:
        model = BreakId
        sqla_session = db.session

    channel = fields.Nested('BreakIdChannelSchema', default=None)
    cpsu = fields.Nested('BreakIdCpsuSchema', default=[], many=True)


class CpsuSchema(ma.ModelSchema):
    class Meta:
        model = Cpsu
        sqla_session = db.session

    breakid = fields.Nested('ChannelBreakIdSchema', default=None)


class ChannelBreakIdSchema(ma.ModelSchema):
    breakid_id = fields.Int()
    channel_id = fields.Int()
    breakid = fields.Int()
    casu_adid = fields.Int()
    instime = fields.Str()


class BreakIdChannelSchema(ma.ModelSchema):
    channel_id = fields.Int()
    channel = fields.Str()


class BreakIdCpsuSchema(ma.ModelSchema):
    cpsu_id = fields.Int()
    breakid_id = fields.Int()
    duration = fields.Float()
    flag_mask = fields.Int()
    full_play_flag = fields.Int()
    profile = fields.Int()
    sdv_result = fields.Int()
    stb_mac = fields.Str()
