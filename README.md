🎮 Player Journey Analytics Dashboard
A browser-based analytics tool for visualising player behaviour across matches — built for Level Designers to explore movement, kills, deaths, loot patterns, and bot vs human activity on a live minimap.

🔗 Live Demo
Hosted URL: (https://github.com/Kadamdarshann/player-journey-tool)

🛠 Tech Stack
Layer
Technology
Frontend + Backend
Python · Streamlit
Data processing
Pandas · PyArrow
Visualisation
Plotly (scatter, heatmap, bar, pie)
Image handling
Pillow · Base64
Hosting
Streamlit Community Cloud


📁 Project Structure
player-journey-tool/
│
├── app.py                        # Main Streamlit application
│
├── data/
│   └── player_data/
│       ├── minimaps/
│       │   ├── AmbroseValley_Minimap.png
│       │   ├── GrandRift_Minimap.png
│       │   └── Lockdown_Minimap.jpg
│       └── **/*.nakama-0         # Parquet data files
│
├── requirements.txt              # Python dependencies
├── README.md                     # This file
├── ARCHITECTURE.md               # System design decisions
└── INSIGHTS.md                   # Three data insights


⚙️ Running Locally
1. Clone the repo
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO

2. Install dependencies
pip install -r requirements.txt

3. Add your data
Make sure your data files are in place:
data/player_data/          ← your .nakama-0 parquet files
data/player_data/minimaps/ ← minimap images

4. Run the app
streamlit run app.py

Then open http://localhost:8501 in your browser.

📦 requirements.txt
streamlit
pandas
plotly
pillow
pyarrow
numpy


🎮 Features
Movement Map — player paths overlaid on the minimap, pinned to game world coordinates
Timeline Slider — replay a match event by event
Human vs Bot — visually distinct markers (circle = human, X = bot)
Event Markers — kills ★, deaths ✖, loot ◆, storm deaths ■, bot events
Heatmaps — kill zones, death zones, loot zones, all-traffic layers
Filters — by map, date, match ID, and individual player
Insights Tabs — player leaderboard, kill timeline, zone analysis, human vs bot breakdown
Metric Cards — live K/D ratio, kills, deaths, loot count per match view

📝 Assumptions
Bot detection: any event containing the string "Bot" is classified as a bot event
Timestamps: stored as Unix seconds, converted to datetime on load
Coordinate system: game world X/Z coordinates mapped directly to Plotly scatter axes; minimap image anchored to match coordinate bounds
Files: all .nakama-0 files under data/player_data/ are treated as parquet

👤 Author
Built as part of a Level Design analytics assignment.

