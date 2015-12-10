from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
from django.utils.dateparse import parse_datetime, parse_date
from django.utils.text import slugify
from django.db.utils import IntegrityError, DataError
from councilmatic_core.models import Person, Bill, Organization, Action, ActionRelatedEntity, \
                        Post, Membership, Sponsorship, LegislativeSession, \
                        Document, BillDocument, Event, EventParticipant, EventDocument, \
                        EventAgendaItem, AgendaItemBill

from dateutil import parser as date_parser

import requests
import json
import pytz
import os.path
import re
import datetime

for configuration in ['OCD_JURISDICTION_ID', 
                      'OCD_CITY_COUNCIL_ID', 
                      'HEADSHOT_PATH',
                      'LEGISLATIVE_SESSIONS'
                      ]:


    if not hasattr(settings, configuration):
        raise ImproperlyConfigured('You must define {0} in settings.py'.format(configuration))

app_timezone = pytz.timezone(settings.TIME_ZONE)
base_url = 'http://ocd.datamade.us'

DEBUG = settings.DEBUG


class Command(BaseCommand):
    help = 'loads in data from the open civic data API'

    def add_arguments(self, parser):
        parser.add_argument('--endpoint', help="a specific endpoint to load data from")
        
        parser.add_argument('--delete',
            action='store_true',
            default=False,
            help='delete data before loading')

    def handle(self, *args, **options):

        if options['endpoint'] == 'organizations':
            self.grab_organizations(delete=options['delete'])
            print("\ndone!", datetime.datetime.now())

        elif options['endpoint'] == 'bills':
            self.grab_bills(delete=options['delete'])
            print("\ndone!", datetime.datetime.now())

        elif options['endpoint'] == 'people':
            self.grab_people(delete=options['delete'])
            print("\ndone!", datetime.datetime.now())

        elif options['endpoint'] == 'events':
            self.grab_events(delete=options['delete'])
            print("\ndone!", datetime.datetime.now())

        else:
            print("\n** LOADING EVERYTHING! **\n")
            self.grab_organizations(delete=options['delete'])
            self.grab_bills(delete=options['delete'])
            self.grab_people(delete=options['delete'])
            self.grab_events(delete=options['delete'])
            print("\ndone!", datetime.datetime.now())
        
    def grab_organizations(self, delete=False):
        print("\nLOADING ORGANIZATIONS", datetime.datetime.now())
        if delete:
            Organization.objects.all().delete()
            Post.objects.all().delete()
            print("deleted all organizations and posts")

        # first grab city council root
        self.grab_organization_posts(settings.OCD_CITY_COUNCIL_ID)

        # this grabs a paginated listing of all organizations within a jurisdiction
        orgs_url = base_url+'/organizations/?jurisdiction_id='+settings.OCD_JURISDICTION_ID
        r = requests.get(orgs_url)
        page_json = json.loads(r.text)

        for i in range(page_json['meta']['max_page']):

            r = requests.get(orgs_url+'&page='+str(i+1))
            page_json = json.loads(r.text)

            for result in page_json['results']:

                self.grab_organization_posts(result['id'])


    def grab_organization_posts(self, organization_ocd_id, parent=None):

        url = base_url+'/'+organization_ocd_id
        r = requests.get(url)
        page_json = json.loads(r.text)

        source_url = ''
        if page_json['sources']:
            source_url = page_json['sources'][0]['url']

        if parent:
            try:
                org_obj, created = Organization.objects.get_or_create(
                        ocd_id=organization_ocd_id,
                        name=page_json['name'],
                        classification=page_json['classification'],
                        source_url=source_url,
                        slug=slugify(page_json['name']),
                        _parent=parent,
                    )
            except IntegrityError:
                ocd_id_part = organization_ocd_id.rsplit('-',1)[1]
                org_obj, created = Organization.objects.get_or_create(
                        ocd_id=organization_ocd_id,
                        name=page_json['name'],
                        classification=page_json['classification'],
                        source_url=source_url,
                        slug=slugify(page_json['name'])+ocd_id_part,
                        _parent=parent,
                    )
        else:
            try:
                org_obj, created = Organization.objects.get_or_create(
                        ocd_id=organization_ocd_id,
                        name=page_json['name'],
                        classification=page_json['classification'],
                        source_url=source_url,
                        slug=slugify(page_json['name']),
                    )
            except IntegrityError:
                ocd_id_part = organization_ocd_id.rsplit('-',1)[1]
                org_obj, created = Organization.objects.get_or_create(
                        ocd_id=organization_ocd_id,
                        name=page_json['name'],
                        classification=page_json['classification'],
                        source_url=source_url,
                        slug=slugify(page_json['name'])+ocd_id_part,
                    )

        # if created and DEBUG:
        #     print('   adding organization: %s' % org_obj.name )
        if created and DEBUG:
            print('\u263A', end=' ', flush=True)

        for post_json in page_json['posts']:

            obj, created = Post.objects.get_or_create(
                    ocd_id = post_json['id'],
                    label = post_json['label'],
                    role = post_json['role'],
                    _organization = org_obj,
                )

            # if created and DEBUG:
            #     print('      adding post: %s %s' %(post_json['role'], post_json['label']))

        for child in page_json['children']:
            self.grab_organization_posts(child['id'], org_obj)


    def grab_people(self, delete=False):
        # find people associated with existing organizations & bills

        print("\nLOADING PEOPLE", datetime.datetime.now())
        if delete:
            Person.objects.all().delete()
            Membership.objects.all().delete()
            Sponsorship.objects.all().delete()
            print("deleted all people, memberships, sponsorships")

        # grab people associated with all existing organizations
        orgs = Organization.objects.exclude(name='Democratic').exclude(name='Republican').all()
        for organization in orgs:
            url = base_url+'/'+organization.ocd_id
            r = requests.get(url)
            page_json = json.loads(r.text)

            for membership_json in page_json['memberships']:
                self.grab_person_memberships(membership_json['person']['id'])

        # add sponsorships for all existing bills
        bills = Bill.objects.all()
        for bill in bills:
            url = base_url+'/'+bill.ocd_id
            r = requests.get(url)
            page_json = json.loads(r.text)

            for sponsor_json in page_json['sponsorships']:
                sponsor=Person.objects.filter(ocd_id=sponsor_json['entity_id']).first()
                if sponsor:
                    obj, created = Sponsorship.objects.get_or_create(
                            _bill=bill,
                            _person=sponsor,
                            classification=sponsor_json['classification'],
                            is_primary=sponsor_json['primary'],
                        )

                    # if created and DEBUG:
                    #     print('      adding sponsorship: %s %s' % (obj.bill, obj.person))
    

    def grab_bills(self, delete=False):
        # this grabs all bills & associated actions, documents from city council
        # organizations need to be populated before bills & actions are populated

        print("\nLOADING BILLS", datetime.datetime.now())
        if delete:
            Bill.objects.all().delete()
            Action.objects.all().delete()
            ActionRelatedEntity.objects.all().delete()
            LegislativeSession.objects.all().delete()
            Document.objects.all().delete()
            BillDocument.objects.all().delete()
            print("deleted all bills, actions, legislative sessions, documents\n")

        # get legislative sessions
        self.grab_legislative_sessions()

        if delete:
            # everything is deleted, grab all legislative sessions
            leg_sessions_to_grab = settings.LEGISLATIVE_SESSIONS
            updated_at_filter = ''
        else:
            # otherwise, only look at most recent legislative session & only
            # look at stuff that has been updated since most recent Bill.ocd_updated_at value
            leg_sessions_to_grab = [settings.LEGISLATIVE_SESSIONS[-1]]
            most_recent_date = Bill.objects.all().order_by('-ocd_updated_at').first().ocd_updated_at.isoformat()
            most_recent_date = most_recent_date.split('+')[0]
            ocd_id = Bill.objects.all().order_by('-ocd_updated_at').first().ocd_id

            print("only looking at bills on the ocd api that have been updated since %s" %most_recent_date)
            updated_at_filter = '&updated_at__gte=%s' %most_recent_date


        for leg_session in leg_sessions_to_grab:
            bill_url = base_url+'/bills/?from_organization_id=%s&legislative_session__identifier=%s%s' % (settings.OCD_CITY_COUNCIL_ID,leg_session, updated_at_filter)

            print("\nadding bills: %s legislative session" %leg_session)
            r = requests.get(bill_url)
            page_json = json.loads(r.text)

            for i in range(page_json['meta']['max_page']):

                r = requests.get(bill_url+'&page='+str(i+1))
                page_json = json.loads(r.text)

                for result in page_json['results']:
                    self.grab_bill(result['id'])

    def grab_legislative_sessions(self):

        # TO-DO: update this when ocd data is fixed

        for leg_session in settings.LEGISLATIVE_SESSIONS:
            obj, created = LegislativeSession.objects.get_or_create(
                    identifier=leg_session,
                    jurisdiction_ocd_id=settings.OCD_JURISDICTION_ID,
                    name='%s Legislative Session' %leg_session,
                )
            if created and DEBUG:
                print('adding legislative session: %s' %obj.name)

    def grab_bill(self, bill_id):

        bill_url = base_url+'/'+bill_id
        r = requests.get(bill_url)
        page_json = json.loads(r.text)

        from_org = Organization.objects.filter(ocd_id=page_json['from_organization']['id']).first()
        legislative_session = LegislativeSession.objects.filter(identifier=page_json['legislative_session']['identifier']).first()
        
        if page_json['extras'].get('local_classification'):
            bill_type = page_json['extras']['local_classification']
        elif len(page_json['classification']) == 1:
            bill_type = page_json['classification'][0]
        else:
            raise Exception(page_json['classification'])


        if 'full_text' in page_json['extras']:
            full_text = page_json['extras']['full_text']
        else:
            full_text = ''

        if page_json['abstracts']:
            abstract = page_json['abstracts'][0]['abstract']
        else:
            abstract = ''

        bill_fields = {
            'ocd_id': bill_id,
            'ocd_created_at':page_json['created_at'],
            'ocd_updated_at':page_json['updated_at'],
            'description':page_json['title'],
            'identifier':page_json['identifier'],
            'classification':page_json['classification'][0],
            'source_url':page_json['sources'][0]['url'],
            'source_note':page_json['sources'][0]['note'],
            '_from_organization':from_org,
            'full_text':full_text,
            'abstract':abstract,
            '_legislative_session':legislative_session,
            'bill_type':bill_type,
        }

        # look for existing bill
        try:
            obj = Bill.objects.get(ocd_id=bill_id)

            # check if it has been updated on api
            if obj.ocd_updated_at.isoformat() != page_json['updated_at']:

                obj.ocd_created_at=page_json['created_at']
                obj.ocd_updated_at=page_json['updated_at']
                obj.description=page_json['title']
                obj.identifier=page_json['identifier']
                obj.classification=page_json['classification'][0]
                obj.source_url=page_json['sources'][0]['url']
                obj.source_note=page_json['sources'][0]['note']
                obj._from_organization=from_org
                obj.full_text=full_text
                obj.abstract=abstract
                obj._legislative_session=legislative_session
                obj.bill_type=bill_type

                obj.save()

                if DEBUG:
                    print('\u270E', end=' ', flush=True)

        # except if it doesn't exist, we need to make it
        except Bill.DoesNotExist:

            try:
                bill_fields['slug'] = slugify(page_json['identifier'])
                obj, created = Bill.objects.get_or_create(**bill_fields)

            except IntegrityError:
                ocd_id_part = bill_id.rsplit('-',1)[1]
                bill_fields['slug'] = slugify(page_json['identifier'])+ocd_id_part
                obj, created = Bill.objects.get_or_create(**bill_fields)

            if created and DEBUG:
                print('\u263A', end=' ', flush=True)

        action_order = 0
        for action_json in page_json['actions']:
            self.load_action(action_json, obj, action_order)
            action_order+=1

        # update bill last_action_date with most recent action
        obj.last_action_date = obj.get_last_action_date()
        obj.save()

        # update documents associated with a bill
        for document_json in page_json['documents']:
            self.load_bill_document(document_json, obj)



    def load_action(self, action_json, bill, action_order):

        org = Organization.objects.filter(ocd_id=action_json['organization']['id']).first()

        classification = ""
        if action_json['classification']:
            classification = action_json['classification'][0]
        
        action_date = app_timezone.localize(date_parser.parse(action_json['date']))

        action_obj, created = Action.objects.get_or_create(
                date=action_date,
                classification=classification,
                description=action_json['description'],
                _organization=org,
                _bill=bill,
                order=action_order,
            )

        # if created and DEBUG:
        #     print('      adding action: %s' %action_json['description'])

        for related_entity_json in action_json['related_entities']:

            action_related_entity = {
                '_action': action_obj,
                'entity_name': related_entity_json['name'],
                'entity_type': related_entity_json['entity_type'],
                'organization_ocd_id': '',
                'person_ocd_id': '',
            }
            
            if related_entity_json['entity_type'] == 'organization':
 
                if not related_entity_json['organization_id']:
                    org = Organization.objects.filter(name=action_related_entity['entity_name']).first()
                    if org:
                        action_related_entity['organization_ocd_id'] = org.ocd_id
                    else:
                        raise Exception('organization called {0} does not exist'\
                                            .format(action_related_entity['entity_name']))
                else:
                    action_related_entity['organization_ocd_id'] = related_entity_json['organization_id']
            
            elif related_entity_json['entity_type'] == 'person':
                
                if not related_entity_json['person_id']:
                    org = Person.objects.filter(name=action_related_entity['entity_name']).first()
                    if org:
                        action_related_entity['person_ocd_id'] = org.ocd_id
                    else:
                        raise Exception('person called {0} does not exist'\
                                            .format(action_related_entity['entity_name']))
                else:
                    action_related_entity['person_ocd_id'] = related_entity_json['person_id']

            obj, created = ActionRelatedEntity.objects.get_or_create(**action_related_entity)

            # if created and DEBUG:
            #     print('         adding related entity: %s' %obj.entity_name)

    def load_bill_document(self, document_json, bill):

        doc_obj, created = Document.objects.get_or_create(
                note=document_json['note'],
                url=document_json['links'][0]['url'],
            )

        obj, created = BillDocument.objects.get_or_create(
                bill = bill,
                document = doc_obj,
            )

        # if created and DEBUG:
        #     print('      adding document: %s' % doc_obj.note)


    def grab_person_memberships(self, person_id):
        # this grabs a person and all their memberships

        url = base_url+'/'+person_id
        r = requests.get(url)
        page_json = json.loads(r.text)

        # TO DO: handle updating people & memberships
        person = Person.objects.filter(ocd_id=person_id).first()
        if not person:

            # save image to disk
            if page_json['image']:
                r = requests.get(page_json['image'], verify=False)
                if r.status_code == 200:
                    with open((settings.HEADSHOT_PATH + page_json['id'] + ".jpg"), 'wb') as f:
                        for chunk in r.iter_content(1000):
                            f.write(chunk)
                            f.flush()

            email = ''
            for contact_detail in page_json['contact_details']:
                if contact_detail['type'] == 'email':
                    if contact_detail['value'] != 'mailto:':
                        email = contact_detail['value']

            website_url = ''
            for link in page_json['links']:
                if link['note'] == "web site":
                    website_url = link['url']


            try:
                person = Person.objects.create(
                    ocd_id=page_json['id'],
                    name=page_json['name'],
                    headshot=page_json['image'],
                    source_url=page_json['sources'][0]['url'],
                    source_note=page_json['sources'][0]['note'],
                    website_url = website_url,
                    email = email,
                    slug=slugify(page_json['name']),
                )
            except IntegrityError:
                ocd_id_part=page_json['id'].rsplit('-',1)[1]
                person = Person.objects.create(
                    ocd_id=page_json['id'],
                    name=page_json['name'],
                    headshot=page_json['image'],
                    source_url=page_json['sources'][0]['url'],
                    source_note=page_json['sources'][0]['note'],
                    website_url = '',
                    email = email,
                    slug=slugify(page_json['name'])+ocd_id_part,
                )

            # if DEBUG:
            #     print('   adding person: %s' % person.name)
            if DEBUG:
                print('\u263A', end=' ', flush=True)

        for membership_json in page_json['memberships']:

            if membership_json['post']:
                post = Post.objects.filter(ocd_id=membership_json['post']['id']).first()
            else:
                post = None

            organization = Organization.objects.filter(ocd_id=membership_json['organization']['id']).first()
            # adding republican or democratic party when encountered
            # b/c parties are not added when organizations are loaded (in grab_organizations)
            if not organization and membership_json['organization']['name'] in ['Republican', 'Democratic']:
                self.grab_organization_posts(membership_json['organization']['id'])
                organization = Organization.objects.filter(ocd_id=membership_json['organization']['id']).first()

            try:
                end_date = parse_date(membership_json['end_date'])
            except:
                end_date = None
            try:
                start_date = parse_date(membership_json['start_date'])
            except:
                start_date = None

            obj, created = Membership.objects.get_or_create(
                    _organization = organization,
                    _person = person,
                    _post = post,
                    label = membership_json['label'],
                    role = membership_json['role'],
                    start_date = start_date,
                    end_date = end_date
                )

            # if created and DEBUG:
            #     print('      adding membership: %s' % obj.role)

    def grab_events(self, delete=False):

        print("\nLOADING EVENTS", datetime.datetime.now())
        if delete:
            Event.objects.all().delete()
            EventParticipant.objects.all().delete()
            EventDocument.objects.all().delete()
            EventAgendaItem.objects.all().delete()
            AgendaItemBill.objects.all().delete()
            print("deleted all events, participants, documents, agenda items, agenda item bill references")

        # this grabs a paginated listing of all events within a jurisdiction
        events_url = base_url+'/events/?jurisdiction_id='+settings.OCD_JURISDICTION_ID
        r = requests.get(events_url)
        page_json = json.loads(r.text)

        for i in range(page_json['meta']['max_page']):

            r = requests.get(events_url+'&page='+str(i+1))
            page_json = json.loads(r.text)

            for result in page_json['results']:
                self.grab_event(result['id'])

    def grab_event(self, event_ocd_id):

        event_url = base_url+'/'+event_ocd_id
        r = requests.get(event_url)


        if r.status_code == 200:
            page_json = json.loads(r.text)

            try:
                legistar_id = re.findall('ID=(.*)&GUID', page_json['sources'][0]['url'])[0]
            except:
                print("\n\n"+"-"*60)
                print("WARNING: MISSING SOURCE %s" %event_ocd_id)
                print("event has no source")
                print("-"*60+"\n")
                legistar_id = event_ocd_id

            try:
                event_obj, created = Event.objects.get_or_create(
                        ocd_id = event_ocd_id,
                        ocd_created_at=page_json['created_at'],
                        ocd_updated_at=page_json['updated_at'],
                        name = page_json['name'],
                        description = page_json['description'],
                        classification = page_json['classification'],
                        start_time = parse_datetime(page_json['start_time']),
                        end_time = parse_datetime(page_json['end_time']) if page_json['end_time'] else None,
                        all_day = page_json['all_day'],
                        status = page_json['status'],
                        location_name = page_json['location']['name'],
                        location_url = page_json['location']['url'],
                        source_url = page_json['sources'][0]['url'],
                        source_note = page_json['sources'][0]['note'],
                        slug = legistar_id,
                    )

            except IntegrityError:
                event_obj, created = Event.objects.get_or_create(
                        ocd_id = event_ocd_id,
                        ocd_created_at=page_json['created_at'],
                        ocd_updated_at=page_json['updated_at'],
                        name = page_json['name'],
                        description = page_json['description'],
                        classification = page_json['classification'],
                        start_time = parse_datetime(page_json['start_time']),
                        end_time = parse_datetime(page_json['end_time']) if page_json['end_time'] else None,
                        all_day = page_json['all_day'],
                        status = page_json['status'],
                        location_name = page_json['location']['name'],
                        location_url = page_json['location']['url'],
                        source_url = page_json['sources'][0]['url'],
                        source_note = page_json['sources'][0]['note'],
                        slug = event_ocd_id,
                    )
                print("\n\n"+"-"*60)
                print("WARNING: SLUG ALREADY EXISTS FOR %s" %event_ocd_id)
                print("legistar id (what slug should be): %s" %legistar_id)
                print("using ocd id as slug instead")
                print("-"*60+"\n")

            # if created and DEBUG:
            #     print('   adding event: %s' % event_ocd_id)
            if created and DEBUG:
                print('\u263A', end=' ', flush=True)

            for participant_json in page_json['participants']:
                obj, created = EventParticipant.objects.get_or_create(
                        event = event_obj,
                        note = participant_json['note'],
                        entity_name = participant_json['entity_name'],
                        entity_type = participant_json['entity_type']
                    )
                # if created and DEBUG:
                #     print('      adding participant: %s' %obj.entity_name)

            for document_json in page_json['documents']:
                self.load_eventdocument(document_json, event_obj)

            for agenda_item_json in page_json['agenda']:
                self.load_eventagendaitem(agenda_item_json, event_obj)

        else:
            print("\n\n"+"*"*60)
            print("SKIPPING EVENT %s" %event_ocd_id)
            print("cannot retrieve event data")
            print("*"*60+"\n")

    def load_eventagendaitem(self, agenda_item_json, event):

        agendaitem_obj, created = EventAgendaItem.objects.get_or_create(
                event = event,
                order = agenda_item_json['order'],
                description = agenda_item_json['description'],
            )

        # if created and DEBUG:
        #     print('      adding agenda item: %s' %agendaitem_obj.order)

        if agenda_item_json['related_entities']:
            related_entity_json = agenda_item_json['related_entities'][0]
            clean_bill_identifier = re.sub(' 0', ' ', related_entity_json['entity_name'])
            related_bill = Bill.objects.filter(identifier = clean_bill_identifier).first()

            if related_bill:
                obj, created = AgendaItemBill.objects.get_or_create(
                        agenda_item = agendaitem_obj,
                        bill = related_bill,
                        note = related_entity_json['note'],
                    )

            # if created and DEBUG:
            #     print('         adding related bill: %s' %related_bill.identifier)


    def load_eventdocument(self, document_json, event):

        doc_obj, created = Document.objects.get_or_create(
                note=document_json['note'],
                url=document_json['links'][0]['url'],
            )

        obj, created = EventDocument.objects.get_or_create(
                event = event,
                document = doc_obj,
            )

        # if created and DEBUG:
        #     print('      adding document: %s' % doc_obj.note)
