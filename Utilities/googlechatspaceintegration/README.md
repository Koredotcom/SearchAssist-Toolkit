
# set up the environment to use google workspace environment
follow the below documentation for the set up:
link: https://developers.google.com/workspace/chat/api/guides/quickstart/nodejs

# set up webhook triggers
 1. Go to script.google.com.
 2. Go to "getting started" tab.
 3. Choose the prebuilt "ChatApp" project.
 4. Inside "onMessage" event listener replace your code.
 5. The code inside the onMessage event listener sholud call your '/webhook'     
    endpoint which sends the message and thread name as request body.
 6. Now deploy the project as add-on and copy the deploymentId.
 7. Go to google cloud console, configure your google chat App.
 8. In the connection settings choose "Apps script".
 9. Paste the deploymentId.
 10. Save the configuration.

 # set up incoming webhooks
 1. go to your google chats workspace.
 2. Open space settings.
 3. Go to Apps & Integrations.
 4. Add the webhook and copy the url.
 5. paste that webhook url in you .env file as follows:
     WEBHOOK_URL = <your-webhook-url>

# To run the server
 Go to root folder
  1. install dependencies: npm install
  2. to run server: node index.js