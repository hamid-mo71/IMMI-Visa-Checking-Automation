import requests as rq
import json
import time
from pprint import pprint

def make_simple_login(username, password):
    payload = {
        'DeviceId': 'device-id',
        'Username': username,
        'Password': password
    }

    test_payload = {
	"CallbackUrl":"String content",
	"DeviceId":"String content",
	"SessionId":"String content"
    }
    r = rq.post('https://tvs.idvpacific.com.au/vpe.svc/session/login/', json=payload)

    if r.json()['SessionId']:
        return r.json()['SessionId']
    else:
        return None


def get_inbox_content(session_id):
    payload = {
        'DeviceId': 'device-id',
        'SessionId': session_id,
    }

    r = rq.post('https://tvs.idvpacific.com.au/vpe.svc/inbox/query/', json=payload)
    
    if r.json()['Success'] == True:
        return r.json()
    else:
        return None

def get_pending_content(session_id):
    payload = {
    'DeviceId': 'device-id',
    'SessionId': session_id,
    'InboxItems': [],
    'FetchPending': True
    }

    r = rq.post('https://tvs.idvpacific.com.au/vpe.svc/inbox/queryChanges/', json=payload)
    
    if r.json()['Success'] == True:
        return r.json()
    else:
        return None


def create_empty_application(session_id):
    """
    STEP 1
    """
    
    payload = {
    'DeviceId': 'device-id',
    'SessionId': session_id,
    'DocumentSource': 4
    }
    
    r = rq.post('https://tvs.idvpacific.com.au/vpe.svc/dataAccess/createDocumentContainer/', json=payload)
    
    if r.json()['Success'] == True:
        return r.json()['ContainerId']
    else:
        return None


def create_new_application(session_id, container_id):
    """
    STEP 2
    """
    payload = {
    'DeviceId': 'device-id',
    'SessionId': session_id,
    'ContainerId': container_id
    }

    r = rq.post('https://tvs.idvpacific.com.au/vpe.svc/dataAccess/createDocument/', json=payload)
    if r.json()['Success'] == True:
        return r.json()['DocumentId']
    else:
        return None


def upload_document_image(session_id, container_id, document_id, file_name):
    """
    STEP 3
    """
    data = open(file_name, 'rb').read()
    
    headers = {
        'Content-Type': 'application/octet-stream',
        '__TT_DeviceId': 'device-id',
        '__TT_SessionId': session_id,
        
    }
    #
    r = rq.post(f'https://tvs.idvpacific.com.au/vpe.svc/dataAccess/uploadImage/?__TT_ContainerId={container_id}&__TT_DocumentId={document_id}&__TT_ImageType=2', data=data, headers=headers)
    

    if r.json()['Success'] == True:
        return r.json()['ImageId']
    else:
        return None


def publish_document_container(session_id, container_id):
    """
    STEP 4
    """
    payload = {
    'DeviceId': 'device-id',
    'SessionId': session_id,
    'ContainerId': container_id,
    'WebClientRequest': True,
    'AutoReferral': True
    }
    r = rq.post('https://tvs.idvpacific.com.au/vpe.svc/dataAccess/publishDocumentContainer/', json=payload)
    if r.json()['Success'] == True:
        return True
    else:
        return None

def retrieving_application(session_id,container_id,document_id):
    """
    STEP 5
    """
    time.sleep(10)
    payload = {
        'DeviceId': 'device-id',
        'SessionId': session_id,
        'ContainerId': container_id,
        'DocumentId': document_id
    }

    r = rq.post('https://tvs.idvpacific.com.au/vpe.svc/dataAccess/retrieveDocument',json=payload)
    r2 = r.content
    response = json.loads(r2.decode('utf-8'))
    print(response['Document']['DocumentFields'])

def do_four_steps(session_id, file_name):
    container_id = create_empty_application(session_id)
    if container_id:
        print(f'STEP 1: {container_id}')
        document_id = create_new_application(session_id, container_id)
        if document_id:
            print(f'STEP 2: {document_id}')
            image_id = upload_document_image(session_id, container_id, document_id, file_name)
            if image_id:
                print(f'STEP 3: {image_id}')
                published = publish_document_container(session_id, container_id)
                if published:
                    print('STEP 4: DONE')
                    retrieving_application(session_id,container_id,document_id)
                    return True
    return False
                    
        
    

def print_result(json_data):
    print(json.dumps(json_data, indent=4, sort_keys=True))

session_id = make_simple_login('admin','PKCAKMIDVPacific77')
#print(json.dumps(make_simple_login('admin','trustid'), indent=4, sort_keys=True))

print(do_four_steps(session_id, '2.jpg'))

#print_result(get_pending_content(session_id))

