"use strict";
//Declaration
const jsonSize = require("json-size");

//Setup Client
const Client = require("ibmiotf");
let appClientConfig = {
    "org" : "29esfy",
    "id" : "CostCalculator",
    "auth-key" : "a-29esfy-2mtus6l9pj",
    "auth-token" :"m_If0Ke0Pm-msFN3yx"
};

let appClient = new Client.IotfApplication(appClientConfig);

//Setup Json
let myJson = {"d":{
  "Name": "Brempton",
  "Nachname": "Genetikks",
  "Alter": 300,
  "Geburtsdatum": "24.07.2070",
  "Beruf": "R"
  }
};

//Calculate Size of Json
let size = jsonSize(myJson);
console.log("Size of the json:" + size + " byte");
let today = new Date().toISOString().replace(/T.+/, '');
console.log("Today: " + today);

appClient.connect();

//on-Connect-start pushing
appClient.on("connect", function () {
    //publishing event using the default quality of service
    //variables
    let start = Date.now();



    let counter = 0;

    let jsonMax = 10;

    //json push to plattform
    for(let i = 1; i<=jsonMax;i++){
      appClient.publishDeviceEvent("SimDevice","SimDevice", "myEvent", "json", JSON.stringify(myJson), 0, () => {
          counter++;
          if(i == jsonMax) {
              console.log("messages sent: "+ counter+".");
              appClient.getDataUsage(today, today).then(function(data){
                console.log(data);
              });
          }
      });
  };
    //Consolelog whether all jsons are sent or not
  let end = Date.now();
  console.log("Sending the messages took " + ((end - start) / 1000) + " seconds");
  appClient.disconnect();
});

appClient.on("error", function (err) {
    console.log("An wild error appeard! : "+err);
});
