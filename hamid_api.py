import asyncio
import os
import urllib
import datetime

from multidict import MultiDict
from aiohttp import web
from aiohttp import ClientSession, FormData
import aiohttp_jinja2
import jinja2
from bs4 import BeautifulSoup


def json_date_as_datetime(jd):
    sign = jd[-7]
    if sign not in '-+' or len(jd) == 13:
        millisecs = int(jd[6:-2])
    else:
        millisecs = int(jd[6:-7])
        hh = int(jd[-7:-4])
        mm = int(jd[-4:-2])
        if sign == '-': mm = -mm
        millisecs += (hh * 60 + mm) * 60000
    return datetime.datetime(1970, 1, 1) \
        + datetime.timedelta(microseconds=millisecs * 1000)


def datetime_as_iso(dt):
    return dt.strftime("%Y-%m-%d")


async def tvs_login(username, password):
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
    async with ClientSession(headers={"Connection": "close"}) as session:
        async with session.post('https://tvs.idvpacific.com.au/vpe.svc/session/login/', json=payload) as resp:
            json_data = await resp.json()

            if json_data['SessionId']:
                return json_data['SessionId']
            else:
                return None


async def login(username, password):
    """Get a login session with the provided username and password"""
    payload = {
        'username': username,
        'password': password,
        'wc_t': '',
        'wc_s': '',
        'login': 'x',
    }
    async with ClientSession(headers={"Connection": "close"}) as session:
        url = 'https://online.immi.gov.au/lusc/login'

        async with session.get(url) as resp:
            html = await resp.text()
            soup = BeautifulSoup(html, 'html.parser')
            payload['wc_t'] = soup.find('input', attrs={'name':'wc_t'})['value']
            payload['wc_s'] = int(soup.find('input', attrs={'name':'wc_s'})['value'])
            payload = FormData(payload)

        async with session.post(url, data=payload) as resp:
            html = await resp.text()
            assert 'Login successful' in html

        async with session.get('https://online.immi.gov.au/usm/services') as resp:
            html = await resp.text()
            soup = BeautifulSoup(html, 'html.parser')
            # print(resp.status, html)
            payload = {
                'wc_t': soup.find('input', attrs={'name':'wc_t'})['value'],
                'wc_s': int(soup.find('input', attrs={'name':'wc_s'})['value']),
                'continue': 'x',
            }
            payload = FormData(payload)

        async with session.post(url, data=payload) as resp:

            html = await resp.text()
            return session.cookie_jar


async def create_empty_application(session, session_id):
    """
    STEP 1
    """
    
    payload = {
    'DeviceId': 'device-id',
    'SessionId': session_id,
    'DocumentSource': 4
    }
    async with session.post('https://tvs.idvpacific.com.au/vpe.svc/dataAccess/createDocumentContainer/', json=payload) as resp:
        json_data = await resp.json()
    
        if json_data['Success'] == True:
            return json_data['ContainerId']
        else:
            return None


async def create_new_application(session, session_id, container_id):
    """
    STEP 2
    """
    payload = {
    'DeviceId': 'device-id',
    'SessionId': session_id,
    'ContainerId': container_id
    }
    async with session.post('https://tvs.idvpacific.com.au/vpe.svc/dataAccess/createDocument/', json=payload) as resp:
        json_data = await resp.json()

        if json_data['Success'] == True:
            return json_data['DocumentId']
        else:
            return None


async def upload_document_image(session, session_id, container_id, document_id, file_content):
    """
    STEP 3
    """
    # data = open(file_name, 'rb').read()
    
    headers = {
        'Content-Type': 'application/octet-stream',
        '__TT_DeviceId': 'device-id',
        '__TT_SessionId': session_id,
        
    }

    async with session.post(f'https://tvs.idvpacific.com.au/vpe.svc/dataAccess/uploadImage/?__TT_ContainerId={container_id}&__TT_DocumentId={document_id}&__TT_ImageType=2', data=file_content, headers=headers) as resp:
        json_data = await resp.json()

        if json_data['Success'] == True:
            return json_data['ImageId']
        else:
            return None


async def publish_document_container(session, session_id, container_id):
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
    async with session.post('https://tvs.idvpacific.com.au/vpe.svc/dataAccess/publishDocumentContainer/', json=payload) as resp:
        json_data = await resp.json()
        if json_data['Success'] == True:
            return True
        else:
            return None


async def retrieving_application(session, session_id,container_id,document_id):
    """
    STEP 5
    """
    # time.sleep(10)
    await asyncio.sleep(12)
    payload = {
        'DeviceId': 'device-id',
        'SessionId': session_id,
        'ContainerId': container_id,
        'DocumentId': document_id
    }
    async with session.post('https://tvs.idvpacific.com.au/vpe.svc/dataAccess/retrieveDocument', json=payload) as resp:
        json_data = await resp.json()
        result = {}
        for field in json_data['Document']['DocumentFields']:
            if field['DisplayName'] in ('Document Number', 'Firstname','Surname','Birth Date','Nationality'):
                if field['DisplayName'].endswith('Date'):
                    result[field['DisplayName']] = datetime_as_iso(json_date_as_datetime(field['FieldValueDate'])) 
                    continue
                result[field['DisplayName']] = field['FieldValueString']
                
        result['Nationality'] = json_data['Document']['DocumentVersion']['Country']['Mrz']
        return result


async def do_four_steps(session_id, file_content):
    async with ClientSession() as session:
        container_id = await create_empty_application(session, session_id)
        if container_id:
            print(f'STEP 1: {container_id}')
            document_id = await create_new_application(session, session_id, container_id)
            if document_id:
                print(f'STEP 2: {document_id}')
                image_id = await upload_document_image(session, session_id, container_id, document_id, file_content)
                if image_id:
                    print(f'STEP 3: {image_id}')
                    published = await publish_document_container(session, session_id, container_id)
                    if published:
                        print('STEP 4: DONE')
                        json_result = await retrieving_application(session, session_id,container_id,document_id)
                        return json_result
        return False


async def fetch_immi_data(request):
    cookie = await login('peter.christie@idvpacific.com', 'PKCAKMidvImmi77')
    json_result = {}
    is_image_request = False
    
    if request.method == 'POST':
        url = 'https://online.immi.gov.au/evo/thirdParty'
        data = await request.post()
        if len(list(data.items())) == 1:
            image = data['image']
            image_file = image.file
            content = image_file.read()
            tvs_session = await tvs_login('admin','PKCAKMIDVPacific77')
            print(tvs_session)
            json_result = await do_four_steps(tvs_session, content)
            is_image_request = True
            # return web.json_response(json_result)
        if is_image_request:
            payload = {
                    # Name
                    '_2a9a2a0a2c0b0': json_result['Surname'],
                    # Given Name
                    '_2a9a2a0a2c1b0': json_result['Firstname'],
                    # Document Type
                    '_2a9a2a0a2e0a1a': '01',
                    # Date of birth
                    '_2a9a2a0a2g0a1a': json_result['Birth Date'],
                    # Date with dashes and numbers
                    '_2a9a2a0a2g0a1a-date': json_result['Birth Date'],
                    # Document Number
                    '_2a9a2a0a2g0b1a': json_result['Document Number'],
                    # Country of Document
                    '_2a9a2a0a2g0c1a': json_result['Nationality'],
                    # I Agree
                    '_2a9a2a0a2i1b0': 'true',
                    # Button
                    '_2a9a2a0a3b0a': 'x',
                    '_0a2-h': 'x',
                    '_1-h': 'x',
                    # Token Stuff
                    'wc_t': '',
                    'wc_s': '',
                    # Stuff
                    'cprofile_timings': 'interface_controls{time:4,result:1};html_start_load{time:295,result:1};unload_load{time:308,result:1};submit_load{time:5799,result:1};last_click_load_Submit{time:5807,result:1};',

                }
        else:
            if data['family_name'] == '' or  data['given_name']=='' or  data['dash_date_of_birth']=='' or  data['document_number']=='' or data['document_country']=='':
                return web.Response(status=400, text='Bad Request')

            payload = {
                # Name
                '_2a9a2a0a2c0b0': data['family_name'],
                # Given Name
                '_2a9a2a0a2c1b0': data['given_name'],
                # Document Type
                '_2a9a2a0a2e0a1a': '01',
                # Date of birth
                '_2a9a2a0a2g0a1a': data['date_of_birth'],
                # Date with dashes and numbers
                '_2a9a2a0a2g0a1a-date': data['dash_date_of_birth'],
                # Document Number
                '_2a9a2a0a2g0b1a': data['document_number'],
                # Country of Document
                '_2a9a2a0a2g0c1a': data['document_country'],
                # I Agree
                '_2a9a2a0a2i1b0': 'true',
                # Button
                '_2a9a2a0a3b0a': 'x',
                '_0a2-h': 'x',
                '_1-h': 'x',
                # Token Stuff
                'wc_t': '',
                'wc_s': '',
                # Stuff
                'cprofile_timings': 'interface_controls{time:4,result:1};html_start_load{time:295,result:1};unload_load{time:308,result:1};submit_load{time:5799,result:1};last_click_load_Submit{time:5807,result:1};',

            }

        #print(payload)

        async with ClientSession(cookie_jar=cookie,headers={"Connection": "close"}) as session:
            post_data = {
                '_2a9a2a0a2c0b0': '',
                # Given Name
                '_2a9a2a0a2c1b0': '',
                # Document Type
                '_2a9a2a0a2e0a1a': '01',
                'wc_ajax': '_2a9a2a0a2e0a1a',
                '_0a2-h': 'x',
                '_1-h': 'x',

            }
            async with session.get(url) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                post_data['wc_t'] = soup.find('input', attrs={'name':'wc_t'})['value']
                post_data['wc_s'] = int(soup.find('input', attrs={'name':'wc_s'})['value'])
                payload['wc_t'] = post_data['wc_t']
                payload['wc_s'] = post_data['wc_s']
                post_data = FormData(post_data)

            async with session.post(url, data=post_data) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                payload = FormData(payload)
                

            async with session.post(url, data=payload) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                # print(soup)
                assert 'Enquiry details' in html

            
            

           

            soup = soup.find_all('div', id=lambda x: x and x.startswith('_'), attrs={'class': 'wc-field'})
            #print(f'{len(soup)} fields are present.')
            json_data = {}
            for field in soup:
                json_data[field.span.text] = field.div.text
            
            #print(json_data)
            # json_data = {
            #     'enquiry_details': {
            #         'family_name': soup.find('div', id='_2a10a2a0a2b4a').div.text,
            #         'given_names': soup.find('div', id='_2a10a2a0a2b4b').div.text,
            #         'date_of_birth': soup.find('div', id='_2a10a2a0a2b4c').div.text,
            #         'document_number': soup.find('div', id='_2a10a2a0a2b4d').div.text,
            #         'country_of_document': soup.find('div', id='_2a10a2a0a2b4e').div.text,
            #     },
            #     'current_visa_details': {
            #         'category_selected': soup.find('div', id='_2a10a2a0a2b8a').div.text,
            #         'family_name': soup.find('div', id='_2a10a2a0a2b8b').div.text,
            #         'given_name': soup.find('div', id='_2a10a2a0a2b8c').div.text,
            #         'document_number': soup.find('div', id='_2a10a2a0a2b8f').div.text,
            #         'visa_class_subclass': soup.find('div', id='_2a10a2a0a2b8g').div.text,
            #         'education_sector': soup.find('div', id='_2a10a2a0a2b8i').div.text,
            #         'visa_applicant': soup.find('div', id='_2a10a2a0a2b8j').div.text,
            #         'visa_grant_date': soup.find('div', id='_2a10a2a0a2b8ba').div.text,
            #         'visa_expiry_date': soup.find('div', id='_2a10a2a0a2b8bb').div.text,
            #         'location': soup.find('div', id='_2a10a2a0a2b8bc').div.text,
            #         'work_entitlements': soup.find('div', id='_2a10a2a0a2b10a').div.text,
            #         'work_conditions': soup.find('div', id='_2a10a2a0a2b10d').div.text,
            #     }
            # }

            async with session.post(url, data=post_data) as resp:
                html = await resp.text()
            post_data = None
            payload = None
            return web.json_response(json_data)
    return web.Response(text='fine')
            

@aiohttp_jinja2.template('client.html')
async def hello(request):
    return {}


if __name__ == '__main__':

    loop = asyncio.get_event_loop()

    cookie = loop.run_until_complete(login('peter.christie@idvpacific.com', 'PKCAKMidvImmi77'))
    print(cookie)

    # loop.run_until_complete(fetch_immi_data())

    app = web.Application()
    app.add_routes([web.get('/', hello), web.route('*', '/immi-passport', fetch_immi_data)])
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(os.path.dirname(os.path.abspath(__file__))))
    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())

    site = web.TCPSite(runner, '0.0.0.0', 8080)
    loop.run_until_complete(site.start())

    loop.run_forever()
