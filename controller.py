from flask import make_response, abort
from config import db
from models import *
from pprint import pprint

def read_all_channels():
    # cpsu = Cpsu(breakid_id=BreakId.query.filter(BreakId.breakid == breakid).one_or_none().breakid_id)
    all_channels = Channel.query.order_by(Channel.channel).all()

    channel_schema = ChannelSchema(many=True)
    data = channel_schema.dump(all_channels)
    pprint(data)


def read_all_breakids():
    all_breakids = BreakId.query.all()

    breakid_schema = BreakIdSchema(many=True)
    data = breakid_schema.dump(all_breakids)
    pprint(data)


def read_all_cpsus():
    all_cpsus = Cpsu.query.all()

    cpsu_schema = CpsuSchema(many=True)
    data = cpsu_schema.dump(all_cpsus)
    pprint(data)


def update_all():
    pass

"""
A POST request is an attempt to create a new resource from an existing one. 
The existing resource may be the parent of the new one in a data-structure sense, 
the way the root of a tree is the parent of all its leaf nodes. Or the existing resource may be a special 
"factory" resource whose only purpose is to generate other resources. The 
representation sent along with a POST request describes the initial state of 
the new resource. As with PUT, a POST request doesn’t need to include a representation at all.
https://stackoverflow.com/questions/16877968/call-a-server-side-method-on-a-resource-in-a-restful-way
"""
if __name__ == '__main__':
    # read_all_channels()
    # read_all_breakids()
    read_all_cpsus()