import firebase_admin
from firebase_admin import credentials, db

# Path to your Firebase credentials
cred = credentials.Certificate('')

# Initialize the app with a service account, granting admin privileges
firebase_admin.initialize_app(cred, {
   'databaseURL': ''
})

timetable = {
    "Monday": {
        "CS": "08:00-10:00",
        "Data": "10:00-12:00",
        "ML": "13:00-15:00",
        "BD": "15:00-17:00"
    },
    "Tuesday": {
        "Robotics": "08:00-10:00",
        "Algorithms": "10:00-12:00",
        "DL": "13:00-15:00",
        "DS": "15:00-17:00"
    },
    "Wednesday": {
        "AI": "08:00-10:00",
        "CV": "10:00-12:00",
        "NLP": "13:00-15:00"
    },
    "Thursday": {
        "CS": "08:00-10:00",
        "Data": "10:00-12:00",
        "ML": "13:00-15:00",
        "BD": "15:00-17:00"
    },
    "Friday": {
        "Robotics": "08:00-10:00",
        "Algorithms": "10:00-12:00",
        "DL": "13:00-15:00",
        "DS": "15:00-17:00"
    }
}

ref = db.reference('Timetable')
ref.set(timetable)
print("Timetable updated successfully!")