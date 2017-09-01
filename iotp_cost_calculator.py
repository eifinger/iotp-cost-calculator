from cloudant import Cloudant
from cloudant.error import CloudantDatabaseException
import atexit
import os
import json
import time
import ibmiotf.application
import ibmiotf.api
import sys
import uuid

db_name = 'iotp-cost-calculator'
client = None
db = None

device_type = "SimDevice"
device_id = "SimDevice"

wait_time = 1

# Set today
start_date = time.strftime("%Y-%m-%d")
print "Start Date is {}".format(start_date)


# Env Setup
if 'VCAP_SERVICES' in os.environ:
    vcap = json.loads(os.getenv('VCAP_SERVICES'))
    print('Found VCAP_SERVICES')
    print('This means cloud foundry. Setting wait_time to 10800')
    wait_time = 10800
elif os.path.isfile('vcap-local.json'):
    with open('vcap-local.json') as f:
        vcap = json.load(f)
        print('Found local VCAP_SERVICES')
        print('This means dev env. Setting wait_time to 1')
else:
    sys.exit("No vcap found")

# cloudant setup
if 'cloudantNoSQLDB' in vcap:
    creds = vcap['cloudantNoSQLDB'][0]['credentials']
    user = creds['username']
    password = creds['password']
    url = 'https://' + creds['host']
    client = Cloudant(user, password, url=url, connect=True)
    try:
        db = client[db_name]
        if db.exists():
            print("Successfully connected to database {}".format(db_name))
        else:
            db = client.create_database(db_name, throw_on_exists=True)
            print("Successfully created database {}".format(db_name))
    except KeyError:
        db = client.create_database(db_name, throw_on_exists=True)
        print("Successfully created database {}".format(db_name))
    print("Database contains {} documents".format(db.doc_count()))
else:
    sys.exit("No cloudantNoSQLDB in vcap found")

# Log version (git commit hash)
if os.path.isfile('VERSION'):
    with open('VERSION') as f:
        version = f.readline()
        date = f.readline()
        print("Running git commit: {}This was last verified: {}".format(version,date))
else:
    print("Could not find VERSION file")

# Load input jsons
if os.path.isfile('jsonconf.json'):
    with open('jsonconf.json') as f:
        jsonconf = json.load(f)

#Setup ibmiotf
if not 'iotf-service' in vcap:
    sys.exit("No iotf-service in VCAP_SERVICES")

#Setup ibmiotf
appClientConfig = {
    "org": vcap['iotf-service'][0]['credentials']['org'],
    "id": str(uuid.uuid4()),
    "auth-method": "apikey",
    "auth-key": vcap['iotf-service'][0]['credentials']['apiKey'],
    "auth-token": vcap['iotf-service'][0]['credentials']['apiToken'],
  }
appClient = ibmiotf.application.Client(appClientConfig)
apiClient = ibmiotf.api.ApiClient(appClientConfig)


############################ Calculator Code ###################################
print("Starting iotp-cost-calculator")
qos_levels = [0, 1, 2];
sending_times = [10, 100, 1000, 10000, 100000, 1000000];

usage_params = {'start': start_date, 'end': time.strftime("%Y-%m-%d")}
old_usage = apiClient.getDataTraffic(usage_params)
print ("Old Usage Traffic: {}".format(old_usage))

print("Input File contains {} JSON Objects".format(len(jsonconf['sizes'])))
for sending_time in sending_times:
    print("Sending messages {} times.".format(sending_time))
    for jsoninput in jsonconf['sizes']:
        print("JSON input size is: {}".format(jsoninput))
        actual_size = len(json.dumps(jsonconf['sizes'][jsoninput]).encode('utf-8'))
        print("Calculated size is: {}".format(actual_size))
        for qos in qos_levels:
            print("Messages with QoS: {}".format(qos))
            doc_id = str(wait_time) + "_" + str(qos) + "_" + str(sending_time) + "_" + str(actual_size)
            try:
                document = db[doc_id]
                print("Found document containing data for this combination: {}".format(document['_id']))
                time.sleep(1) #Wait 1 second so db calls are not faster than 20/s
                continue
            except KeyError:
                print("Document does not yet exist. Continue...")
            t0 = time.time()
            times_interrupted = 0
            print("Starting to send messages")
            appClient.connect()
            for i in range(0,sending_time):
                if (i+1)%50002 == 0:
                    print("i is {}. Mod is 0. Waiting 60 seconds".format(i))
                    time.sleep(60)
                    times_interrupted+=1
                appClient.publishEvent(device_type, device_id, "calculator-event", "json", jsonconf['sizes'][jsoninput], qos=qos)
            time_took = round(time.time()-t0, 3)-(10*times_interrupted)
            appClient.disconnect()
            print("Finished sending messages")
            print("Took {} seconds".format(time_took))
            print("Waiting {} seconds before getting reported DataUsage".format(wait_time))
            time.sleep(wait_time)
            usage_params = {'start': start_date, 'end': time.strftime("%Y-%m-%d")}
            new_usage = apiClient.getDataTraffic(usage_params)
            print("Data Usage Information: {}".format(new_usage))
            storage_datetime = time.asctime( time.localtime(time.time()) ).replace(" ","-")
            storage_timestamp = time.time()
            information = {"_id": doc_id,"storage_datetime": storage_datetime,"storage_timestamp": storage_timestamp,"old_data_usage": old_usage['total'],"reported_data_usage": new_usage['total'],"delta_data_usage": new_usage['total'] - old_usage['total'],"assumed_delta_data_usage": sending_time * actual_size,"sending_time": sending_time,"qos": qos,"actual_size": actual_size, "time_took": time_took}
            print("Storing information under doc_id: {}".format(doc_id))
            try:
                new_doc = db.create_document(information,throw_on_exists=True)
                if new_doc.exists():
                    print("Successfully stored information")
            except CloudantDatabaseException:
                print("Document was created from another application in the meantime. Skip...")
            old_usage = new_usage
            print("information: {}".format(information))

print("App run finished")

@atexit.register
def shutdown():
    if client:
        client.disconnect()
    if appClient:
        appClient.disconnect()
