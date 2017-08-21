"use strict";
//Declaration
const jsonSize = require("json-size");
const DependencyFactory = require("./dependencyFactory");

let env = DependencyFactory.getEnvironment();
let appClient = DependencyFactory.getIotClient();

//Setup Json
let myJson = {"d":{
  "Name": "Brempton",
  "Nachname": "Genetikks",
  "Alter": 300,
  "Geburtsdatum": "24.07.2070",
  "Beruf": "R"
  }
};
//Start application
console.log("Starting iotp-cost-calculator")
//Calculate Size of Json
let size = jsonSize(myJson);
console.log("Size of the json:" + size + " byte");
let today = new Date().toISOString().replace(/T.+/, '');
console.log("Today: " + today);
appClient.connect();

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
                console.log(data);
              });
          }
      });
  };
    //Consolelog whether all jsons are sent or not
  let end = Date.now();
  console.log("Sending the messages took " + ((end - start) / 1000) + " seconds");
  appClient.disconnect();
  console.log("Appclient disconnected");
  console.log("App run finished");
});

appClient.on("error", function (err) {
    console.log("A wild error appeared! : "+err);
});
