from flask import Flask, render_template, request, send_from_directory, jsonify
from flask_socketio import SocketIO, join_room, leave_room, emit
from werkzeug.utils import secure_filename
import os
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['UPLOAD_FOLDER'] = 'uploads'

socketio = SocketIO(app)
messages = {}  
users = {}     
sid_to_user = {}  

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    file.save(filepath)
    return jsonify({'url': f'/uploads/{filename}'})

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Socket Events
@socketio.on('join')
def handle_join(data):
    username = data['username']
    room = data['room']
    join_room(room)

    sid_to_user[request.sid] = (username, room)

    if room not in users:
        users[room] = []
    if username not in users[room]:
        users[room].append(username)

    if room not in messages:
        messages[room] = []

    emit('user_joined', username, to=room)
    emit('update_users', users[room], to=room)

@socketio.on('send_message')
def handle_send(data):
    room = data['room']
    username = data['username']
    msg_id = str(uuid.uuid4())
    message_data = {
        'id': msg_id,
        'username': username,
        'message': data['message']
    }
    messages[room].append(message_data)
    emit('receive_message', message_data, to=room)

@socketio.on('delete_message')
def handle_delete(data):
    room = data['room']
    msg_id = data['id']
    username = get_username(request.sid)

    for msg in messages.get(room, []):
        if msg['id'] == msg_id and msg['username'] == username:
            messages[room].remove(msg)
            emit('message_deleted', {'id': msg_id}, to=room)
            break

@socketio.on('edit_message')
def handle_edit(data):
    room = data['room']
    msg_id = data['id']
    new_text = data['newText']
    username = get_username(request.sid)

    for msg in messages.get(room, []):
        if msg['id'] == msg_id and msg['username'] == username:
            msg['message'] = new_text
            emit('message_edited', {'id': msg_id, 'newText': new_text}, to=room)
            break

@socketio.on('typing')
def handle_typing(data):
    username = get_username(request.sid)
    emit('user_typing', username, to=data['room'])

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in sid_to_user:
        username, room = sid_to_user[sid]
        if room in users and username in users[room]:
            users[room].remove(username)
            leave_room(room)
            emit('user_left', username, to=room)
            emit('update_users', users[room], to=room)
        del sid_to_user[sid]


def get_username(sid):
    return sid_to_user.get(sid, ('Unknown', ''))[0]

if __name__ == '__main__':
    socketio.run(app, debug=True)
