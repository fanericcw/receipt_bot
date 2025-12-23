# Discord Receipt Bot

## Description
A Discord bot that leverages Google Gemini to parse your receipts and split the costs with you and your friends, without all the hassle!

## Bot Commands
- `$help`: Lists all available commands
- `$receipt [mode] [tip(%)] "[notes]" [mentions]`: Upload a receipt image and mention users to share with
    - `mode` (optional): How users claim a part of the bill
        - `react` (default): Users react to items found in receipt to claim. The amount is split equally among all reacting users if multiple users claim one item
        - `share`: Split the costs among mentioned users according to instructions given in `notes`
    - `tip(%)` (optional): Amount of tip added to the bill. If tip is a percentage, add % to the end of the number. Otherwise just input a number
    - `notes` (`share` only): Instructions for the LLM to split costs. Items can be specified to be split between a subset of mentioned users
    - `mentions` (`share` only): Mention using `@` to include participants to the bill. **Author is included by default**
- `$iou @user amount`: Record that you owe a user a certain amount
- `$owes @user1 @user2`: Check how much user1 owes user2
- `$owed`: Check how much you owe in total in current server
- `$alias name`: Set an alias (`name`) for the LLM to recognize. Once set up, `name` can be used in place of your Discord handle

## Example Command
```
(@LostGirl)
$alias Alice      - This sets Alice as @LostGirl's alias

(@MadHatter)
$alias Hatman    - This sets Hatman as @MadHatter's alias

- Since @LateRabbit has not set up an alias, @MadHatter will have to use their Discord handle
$receipt share 15% "Hatman had the hot dog. Alice and LateRabbit had an iced tea each. Alice and Hatman shared a pizza" @LostGirl @LateRabbit
```

## Bot Hosting
### Prerequisites
- Python 3.8 or higher
- A Discord Bot Token (You can get one by registering your bot here: https://discordapp.com/developers)
- Google Gemini API Key
- Firebase Realtime Database

## Local Development

1. **Clone the repository**
```bash
   git clone https://github.com/fanericcw/receipt_bot.git
   cd receipt-bot
```

2. **Install dependencies**
```bash
   pip install -r requirements.txt
```

3. **Configure environment variables**
   
   Create a `.env` file in the root directory:
```env
   DISCORD_TOKEN=your_discord_bot_token
   GEMINI_API_KEY=your_gemini_api_key
   FIREBASE_DATABASE_URL=https://your-project.firebaseio.com
   FIREBASE_PROJECT_ID=your_project_id
   FIREBASE_PRIVATE_KEY_ID=your_key_id
   FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
   FIREBASE_CLIENT_EMAIL=your_service_account@project.iam.gserviceaccount.com
   FIREBASE_CLIENT_ID=your_client_id
   FIREBASE_CLIENT_CERT_URL=https://www.googleapis.com/robot/v1/metadata/x509/...
```
>  You can also use the .json file containing your Google Cloud service account credentials instead. However, this is not recommended for production hosting since you will have to upload your credentials in a .json file to the hosting service without encrytion

4. **Run the bot**
```bash
   python receipt_bot.py
```
