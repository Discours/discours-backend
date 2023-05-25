from starlette.applications import Starlette
from starlette.routing import Route, Mount
import socketio

sio = socketio.AsyncServer(async_mode='asgi')
app = Starlette(routes=[
    Mount('/', app=socketio.ASGIApp(sio), name="root"),
])

@sio.event
async def connect(sid, environ):
    print('connect ', sid)

@sio.event
async def disconnect(sid):
    print('disconnect ', sid)


@sio.event
async def some_event(sid, data):
    # Handle the event here
    pass

@sio.event
async def new_comment(sid, data):
    # Notify the user of a new comment on their article
    pass

@sio.event
async def comment_reply(sid, data):
    # Notify the user of a reply to their comment
    pass

@sio.event
async def comment_rating(sid, data):
    # Notify the user of a rating on their comment
    pass


@sio.event
async def new_edit(sid, data):
    # Notify the user of a new edit to their text
    pass

@sio.event
async def new_proposal(sid, data):
    # Notify the user of a new proposal to their text
    pass

@sio.event
async def edit_reply(sid, data):
    # Notify the user of a reply to their edit
    pass

@sio.event
async def proposal_reply(sid, data):
    # Notify the user of a reply to their proposal
    pass

@sio.event
async def edit_rating(sid, data):
    # Notify the user of a rating on their edit
    pass

@sio.event
async def material_published(sid, data):
    # Notify the user when their material is published
    pass

@sio.event
async def mentions(sid, data):
    # Notify the user when they are mentioned in an article or comment
    pass

@sio.event
async def new_subscribers(sid, data):
    # Notify the user of new subscribers
    pass

@sio.event
async def new_badges(sid, data):
    # Notify the user of new badges or roles
    pass

@sio.event
async def article_rating(sid, data):
    # Notify the user of a rating on their article
    pass

@sio.event
async def karma_rating(sid, data):
    # Notify the user of a change in their karma
    pass

@sio.event
async def announcements(sid, data):
    # Notify the user of new announcements
    pass

@sio.event
async def tips(sid, data):
    # Send the user some tips
    pass

@sio.event
async def events(sid, data):
    # Notify the user of new events
    pass

sio.emit('some_event', data, room=sid)
