# firestore_manager.py
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# Initialize Firebase Admin SDK
cred = credentials.Certificate('halifileks-discordbot-firebase-adminsdk.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

def post_command_data(user_id, user_name, command_string, command_time, input_string, server_id, command_server_name, channel_id, channel_name):
    """Posts command data to Firestore database."""
    doc_ref = db.collection('commands_logs').document()
    doc_ref.set({
        'ChannelName': channel_name,
        'ChannelID': channel_id,
        'ServerName': command_server_name,
        'ServerID': server_id,
        'Time': command_time,
        'WrittenString': input_string,
        'UsedCommand': command_string,
        'UserNickname': user_name,
        'UserID': user_id
    })
