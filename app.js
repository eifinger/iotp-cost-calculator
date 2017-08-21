"use strict";
const jsonSize = require("json-size");
const Cloudant = require('cloudant');

const DependencyFactory = require("./util/dependencyFactory");

const dbName = "iotp-cost-calculator";

//Setup Json
let myJson = {"d":{
  "Name": "Brempton",
  "Nachname": "Genetikks",
  "Alter": 300,
  "Geburtsdatum": "24.07.2070",
  "Beruf": "R"
  }
};
let size = jsonSize(myJson);
let today = new Date().toISOString().replace(/T.+/, '');

let env = DependencyFactory.getEnvironment();
let appClient = DependencyFactory.getIotClient();

let storage;

initializeCloudant(function(){
  //Start application
  console.log("Starting iotp-cost-calculator")
  //Calculate Size of Json
  console.log("Size of the json: " + size + " byte");
  console.log("Today: " + today);
  appClient.connect();
});



//on-Connect-start pushing
appClient.on("connect", function () {
    console.log("Appclient connected")
    let start = Date.now();
    let counter = 0;
    let jsonMax = 10;

    //json push to plattform
    for(let i = 1; i<=jsonMax;i++){
      appClient.publishDeviceEvent("SimDevice","SimDevice", "myEvent", "json", JSON.stringify(myJson), 0, () => {
          counter++;
          if(i == jsonMax) {
              console.log("Messages sent: "+ counter+".");
              appClient.getDataUsage(today, today).then(function(data){
                console.log("Data Usage information:\n" + JSON.stringify(data));
                let docId = new Date().toISOString().replace(/\..+/, '');
                console.log("Storing data under id " + docId);
                storage.insert(data, docId, function(err, body) {
                  if (!err)
                    console.log("Successfully stored information:\n" + JSON.stringify(body));
                });
              });
          }
      });
  }
  let end = Date.now();
  console.log("Sending the messages took " + ((end - start) / 1000) + " seconds");
  appClient.disconnect();
  console.log("Appclient disconnected");
  console.log("App run finished");
});

appClient.on("error", function (err) {
    console.log("A wild error appeared! : "+err);
});

/**
*/
function initializeCloudant(callback){
  let credentials = DependencyFactory.getCredentials("cloudantNoSQLDB");
  let cloudant = Cloudant({url: credentials.url});
  storage;
  cloudant.db.create(dbName, function(err, data) {
    if(err){ //If database already exists
      console.log("Database exists.");
    } else {
      console.log("Created database.");
    }
  });
  storage = cloudant.db.use(dbName);
  storage.list(function(err, body) {
    if (!err) {
      console.log("Cloudant contains " +  body.rows.length + " documents.");
      callback(storage);

    }
  });
}
