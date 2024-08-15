# firestore_manager.py
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# Initialize Firebase Admin SDK
cred = credentials.Certificate('halifileks-discordbot-firebase-adminsdk.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

async def post_command_data(user_id, user_name, command_string, command_time, input_string, server_id, command_server_name, channel_id, channel_name):
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

async def store_user_wordle_score(user_id, user_name, score, time):
    """Posts Wordle score data to Firestore database."""
    
    doc_ref = db.collection('user_wordle_scores').document(user_id)
    doc = doc_ref.get()
    if doc.exists:
        doc_ref.update({
            'Time': time,
            'Score': score
        })
    else:
        doc_ref.set({
            'UserNickname': user_name,
            'UserID': user_id,
            'Score': score,
            'Time': time
        })

async def get_user_wordle_scores(user_id):
    """Retrieves user's Wordle scores from Firestore database."""
    
    doc_ref = db.collection('user_wordle_scores').document(user_id)
    if doc_ref.get().exists:
        
        query = db.collection('user_wordle_scores').order_by('Time', direction=firestore.Query.DESCENDING).limit(1)
        docs = query.get()
        if len(docs) > 0:
            user_data = docs[0].to_dict()
            print(user_data)
            return user_data.get('Score')
        else:
            return None
    return None

async def get_all_user_scores():
    """Retrieves all user scores from Firestore database."""
    
    scores = []
    query = db.collection('user_wordle_scores').order_by('Score', direction=firestore.Query.DESCENDING)
    docs = query.get()
    
    for doc in docs:
        user_data = doc.to_dict()
        user_name = user_data.get('UserNickname')
        score = user_data.get('Score')
        scores.append((user_name, score))
    
    return scores
