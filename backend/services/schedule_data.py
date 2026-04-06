"""
IPL 2026 Schedule Seed Data — Extracted from Official TATA IPL 2026 PDF
"""

TEAM_SHORT_CODES = {
    "Royal Challengers Bengaluru": "RCB",
    "Sunrisers Hyderabad": "SRH",
    "Mumbai Indians": "MI",
    "Kolkata Knight Riders": "KKR",
    "Rajasthan Royals": "RR",
    "Chennai Super Kings": "CSK",
    "Punjab Kings": "PBKS",
    "Gujarat Titans": "GT",
    "Lucknow Super Giants": "LSG",
    "Delhi Capitals": "DC",
}

# City-to-stadium mapping
CITY_STADIUMS = {
    "Bengaluru": "M. Chinnaswamy Stadium, Bengaluru",
    "Mumbai": "Wankhede Stadium, Mumbai",
    "Chennai": "MA Chidambaram Stadium, Chennai",
    "Kolkata": "Eden Gardens, Kolkata",
    "Hyderabad": "Rajiv Gandhi Intl Cricket Stadium, Hyderabad",
    "Delhi": "Arun Jaitley Stadium, Delhi",
    "Ahmedabad": "Narendra Modi Stadium, Ahmedabad",
    "Lucknow": "BRSABV Ekana Cricket Stadium, Lucknow",
    "Guwahati": "Barsapara Cricket Stadium, Guwahati",
    "Jaipur": "Sawai Mansingh Stadium, Jaipur",
    "New Chandigarh": "PCA New Stadium, New Chandigarh",
    "Dharamshala": "HPCA Stadium, Dharamshala",
    "Raipur": "Shaheed Veer Narayan Singh Intl Stadium, Raipur",
}


def _date_to_iso(date_str: str, time_str: str) -> str:
    """Convert '28-MAR-26' + '7:30 PM' to ISO format GMT."""
    from datetime import datetime
    import pytz

    months = {
        "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
        "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12
    }
    parts = date_str.split("-")
    day = int(parts[0])
    month = months[parts[1].upper()]
    year = 2000 + int(parts[2])

    # Parse time
    time_parts = time_str.replace(" ", "").upper()
    is_pm = "PM" in time_parts
    time_parts = time_parts.replace("PM", "").replace("AM", "")
    h, m = [int(x) for x in time_parts.split(":")]
    if is_pm and h != 12:
        h += 12
    elif not is_pm and h == 12:
        h = 0

    ist = pytz.timezone("Asia/Kolkata")
    dt = ist.localize(datetime(year, month, day, h, m))
    return dt.astimezone(pytz.utc).isoformat().replace("+00:00", "Z")


IPL_2026_SCHEDULE = [
    {"match_number": 1, "team1": "Royal Challengers Bengaluru", "team2": "Sunrisers Hyderabad", "city": "Bengaluru", "date": "28-MAR-26", "time": "7:30 PM"},
    {"match_number": 2, "team1": "Mumbai Indians", "team2": "Kolkata Knight Riders", "city": "Mumbai", "date": "29-MAR-26", "time": "7:30 PM"},
    {"match_number": 3, "team1": "Rajasthan Royals", "team2": "Chennai Super Kings", "city": "Guwahati", "date": "30-MAR-26", "time": "7:30 PM"},
    {"match_number": 4, "team1": "Punjab Kings", "team2": "Gujarat Titans", "city": "New Chandigarh", "date": "31-MAR-26", "time": "7:30 PM"},
    {"match_number": 5, "team1": "Lucknow Super Giants", "team2": "Delhi Capitals", "city": "Lucknow", "date": "01-APR-26", "time": "7:30 PM"},
    {"match_number": 6, "team1": "Kolkata Knight Riders", "team2": "Sunrisers Hyderabad", "city": "Kolkata", "date": "02-APR-26", "time": "7:30 PM"},
    {"match_number": 7, "team1": "Chennai Super Kings", "team2": "Punjab Kings", "city": "Chennai", "date": "03-APR-26", "time": "7:30 PM"},
    {"match_number": 8, "team1": "Delhi Capitals", "team2": "Mumbai Indians", "city": "Delhi", "date": "04-APR-26", "time": "3:30 PM"},
    {"match_number": 9, "team1": "Gujarat Titans", "team2": "Rajasthan Royals", "city": "Ahmedabad", "date": "04-APR-26", "time": "7:30 PM"},
    {"match_number": 10, "team1": "Sunrisers Hyderabad", "team2": "Lucknow Super Giants", "city": "Hyderabad", "date": "05-APR-26", "time": "3:30 PM"},
    {"match_number": 11, "team1": "Royal Challengers Bengaluru", "team2": "Chennai Super Kings", "city": "Bengaluru", "date": "05-APR-26", "time": "7:30 PM"},
    {"match_number": 12, "team1": "Kolkata Knight Riders", "team2": "Punjab Kings", "city": "Kolkata", "date": "06-APR-26", "time": "7:30 PM"},
    {"match_number": 13, "team1": "Rajasthan Royals", "team2": "Mumbai Indians", "city": "Guwahati", "date": "07-APR-26", "time": "7:30 PM"},
    {"match_number": 14, "team1": "Delhi Capitals", "team2": "Gujarat Titans", "city": "Delhi", "date": "08-APR-26", "time": "7:30 PM"},
    {"match_number": 15, "team1": "Kolkata Knight Riders", "team2": "Lucknow Super Giants", "city": "Kolkata", "date": "09-APR-26", "time": "7:30 PM"},
    {"match_number": 16, "team1": "Rajasthan Royals", "team2": "Royal Challengers Bengaluru", "city": "Guwahati", "date": "10-APR-26", "time": "7:30 PM"},
    {"match_number": 17, "team1": "Punjab Kings", "team2": "Sunrisers Hyderabad", "city": "New Chandigarh", "date": "11-APR-26", "time": "3:30 PM"},
    {"match_number": 18, "team1": "Chennai Super Kings", "team2": "Delhi Capitals", "city": "Chennai", "date": "11-APR-26", "time": "7:30 PM"},
    {"match_number": 19, "team1": "Lucknow Super Giants", "team2": "Gujarat Titans", "city": "Lucknow", "date": "12-APR-26", "time": "3:30 PM"},
    {"match_number": 20, "team1": "Mumbai Indians", "team2": "Royal Challengers Bengaluru", "city": "Mumbai", "date": "12-APR-26", "time": "7:30 PM"},
    {"match_number": 21, "team1": "Sunrisers Hyderabad", "team2": "Rajasthan Royals", "city": "Hyderabad", "date": "13-APR-26", "time": "7:30 PM"},
    {"match_number": 22, "team1": "Chennai Super Kings", "team2": "Kolkata Knight Riders", "city": "Chennai", "date": "14-APR-26", "time": "7:30 PM"},
    {"match_number": 23, "team1": "Royal Challengers Bengaluru", "team2": "Lucknow Super Giants", "city": "Bengaluru", "date": "15-APR-26", "time": "7:30 PM"},
    {"match_number": 24, "team1": "Mumbai Indians", "team2": "Punjab Kings", "city": "Mumbai", "date": "16-APR-26", "time": "7:30 PM"},
    {"match_number": 25, "team1": "Gujarat Titans", "team2": "Kolkata Knight Riders", "city": "Ahmedabad", "date": "17-APR-26", "time": "7:30 PM"},
    {"match_number": 26, "team1": "Royal Challengers Bengaluru", "team2": "Delhi Capitals", "city": "Bengaluru", "date": "18-APR-26", "time": "3:30 PM"},
    {"match_number": 27, "team1": "Sunrisers Hyderabad", "team2": "Chennai Super Kings", "city": "Hyderabad", "date": "18-APR-26", "time": "7:30 PM"},
    {"match_number": 28, "team1": "Kolkata Knight Riders", "team2": "Rajasthan Royals", "city": "Kolkata", "date": "19-APR-26", "time": "3:30 PM"},
    {"match_number": 29, "team1": "Punjab Kings", "team2": "Lucknow Super Giants", "city": "New Chandigarh", "date": "19-APR-26", "time": "7:30 PM"},
    {"match_number": 30, "team1": "Gujarat Titans", "team2": "Mumbai Indians", "city": "Ahmedabad", "date": "20-APR-26", "time": "7:30 PM"},
    {"match_number": 31, "team1": "Sunrisers Hyderabad", "team2": "Delhi Capitals", "city": "Hyderabad", "date": "21-APR-26", "time": "7:30 PM"},
    {"match_number": 32, "team1": "Lucknow Super Giants", "team2": "Rajasthan Royals", "city": "Lucknow", "date": "22-APR-26", "time": "7:30 PM"},
    {"match_number": 33, "team1": "Mumbai Indians", "team2": "Chennai Super Kings", "city": "Mumbai", "date": "23-APR-26", "time": "7:30 PM"},
    {"match_number": 34, "team1": "Royal Challengers Bengaluru", "team2": "Gujarat Titans", "city": "Bengaluru", "date": "24-APR-26", "time": "7:30 PM"},
    {"match_number": 35, "team1": "Delhi Capitals", "team2": "Punjab Kings", "city": "Delhi", "date": "25-APR-26", "time": "3:30 PM"},
    {"match_number": 36, "team1": "Rajasthan Royals", "team2": "Sunrisers Hyderabad", "city": "Jaipur", "date": "25-APR-26", "time": "7:30 PM"},
    {"match_number": 37, "team1": "Gujarat Titans", "team2": "Chennai Super Kings", "city": "Ahmedabad", "date": "26-APR-26", "time": "3:30 PM"},
    {"match_number": 38, "team1": "Lucknow Super Giants", "team2": "Kolkata Knight Riders", "city": "Lucknow", "date": "26-APR-26", "time": "7:30 PM"},
    {"match_number": 39, "team1": "Delhi Capitals", "team2": "Royal Challengers Bengaluru", "city": "Delhi", "date": "27-APR-26", "time": "7:30 PM"},
    {"match_number": 40, "team1": "Punjab Kings", "team2": "Rajasthan Royals", "city": "New Chandigarh", "date": "28-APR-26", "time": "7:30 PM"},
    {"match_number": 41, "team1": "Mumbai Indians", "team2": "Sunrisers Hyderabad", "city": "Mumbai", "date": "29-APR-26", "time": "7:30 PM"},
    {"match_number": 42, "team1": "Gujarat Titans", "team2": "Royal Challengers Bengaluru", "city": "Ahmedabad", "date": "30-APR-26", "time": "7:30 PM"},
    {"match_number": 43, "team1": "Rajasthan Royals", "team2": "Delhi Capitals", "city": "Jaipur", "date": "01-MAY-26", "time": "7:30 PM"},
    {"match_number": 44, "team1": "Chennai Super Kings", "team2": "Mumbai Indians", "city": "Chennai", "date": "02-MAY-26", "time": "7:30 PM"},
    {"match_number": 45, "team1": "Sunrisers Hyderabad", "team2": "Kolkata Knight Riders", "city": "Hyderabad", "date": "03-MAY-26", "time": "3:30 PM"},
    {"match_number": 46, "team1": "Gujarat Titans", "team2": "Punjab Kings", "city": "Ahmedabad", "date": "03-MAY-26", "time": "7:30 PM"},
    {"match_number": 47, "team1": "Mumbai Indians", "team2": "Lucknow Super Giants", "city": "Mumbai", "date": "04-MAY-26", "time": "7:30 PM"},
    {"match_number": 48, "team1": "Delhi Capitals", "team2": "Chennai Super Kings", "city": "Delhi", "date": "05-MAY-26", "time": "7:30 PM"},
    {"match_number": 49, "team1": "Sunrisers Hyderabad", "team2": "Punjab Kings", "city": "Hyderabad", "date": "06-MAY-26", "time": "7:30 PM"},
    {"match_number": 50, "team1": "Lucknow Super Giants", "team2": "Royal Challengers Bengaluru", "city": "Lucknow", "date": "07-MAY-26", "time": "7:30 PM"},
    {"match_number": 51, "team1": "Delhi Capitals", "team2": "Kolkata Knight Riders", "city": "Delhi", "date": "08-MAY-26", "time": "7:30 PM"},
    {"match_number": 52, "team1": "Rajasthan Royals", "team2": "Gujarat Titans", "city": "Jaipur", "date": "09-MAY-26", "time": "7:30 PM"},
    {"match_number": 53, "team1": "Chennai Super Kings", "team2": "Lucknow Super Giants", "city": "Chennai", "date": "10-MAY-26", "time": "3:30 PM"},
    {"match_number": 54, "team1": "Royal Challengers Bengaluru", "team2": "Mumbai Indians", "city": "Raipur", "date": "10-MAY-26", "time": "7:30 PM"},
    {"match_number": 55, "team1": "Punjab Kings", "team2": "Delhi Capitals", "city": "Dharamshala", "date": "11-MAY-26", "time": "7:30 PM"},
    {"match_number": 56, "team1": "Gujarat Titans", "team2": "Sunrisers Hyderabad", "city": "Ahmedabad", "date": "12-MAY-26", "time": "7:30 PM"},
    {"match_number": 57, "team1": "Royal Challengers Bengaluru", "team2": "Kolkata Knight Riders", "city": "Raipur", "date": "13-MAY-26", "time": "7:30 PM"},
    {"match_number": 58, "team1": "Punjab Kings", "team2": "Mumbai Indians", "city": "Dharamshala", "date": "14-MAY-26", "time": "7:30 PM"},
    {"match_number": 59, "team1": "Lucknow Super Giants", "team2": "Chennai Super Kings", "city": "Lucknow", "date": "15-MAY-26", "time": "7:30 PM"},
    {"match_number": 60, "team1": "Kolkata Knight Riders", "team2": "Gujarat Titans", "city": "Kolkata", "date": "16-MAY-26", "time": "7:30 PM"},
    {"match_number": 61, "team1": "Punjab Kings", "team2": "Royal Challengers Bengaluru", "city": "Dharamshala", "date": "17-MAY-26", "time": "3:30 PM"},
    {"match_number": 62, "team1": "Delhi Capitals", "team2": "Rajasthan Royals", "city": "Delhi", "date": "17-MAY-26", "time": "7:30 PM"},
    {"match_number": 63, "team1": "Chennai Super Kings", "team2": "Sunrisers Hyderabad", "city": "Chennai", "date": "18-MAY-26", "time": "7:30 PM"},
    {"match_number": 64, "team1": "Rajasthan Royals", "team2": "Lucknow Super Giants", "city": "Jaipur", "date": "19-MAY-26", "time": "7:30 PM"},
    {"match_number": 65, "team1": "Kolkata Knight Riders", "team2": "Mumbai Indians", "city": "Kolkata", "date": "20-MAY-26", "time": "7:30 PM"},
    {"match_number": 66, "team1": "Chennai Super Kings", "team2": "Gujarat Titans", "city": "Chennai", "date": "21-MAY-26", "time": "7:30 PM"},
    {"match_number": 67, "team1": "Sunrisers Hyderabad", "team2": "Royal Challengers Bengaluru", "city": "Hyderabad", "date": "22-MAY-26", "time": "7:30 PM"},
    {"match_number": 68, "team1": "Lucknow Super Giants", "team2": "Punjab Kings", "city": "Lucknow", "date": "23-MAY-26", "time": "7:30 PM"},
    {"match_number": 69, "team1": "Mumbai Indians", "team2": "Rajasthan Royals", "city": "Mumbai", "date": "24-MAY-26", "time": "3:30 PM"},
    {"match_number": 70, "team1": "Kolkata Knight Riders", "team2": "Delhi Capitals", "city": "Kolkata", "date": "24-MAY-26", "time": "7:30 PM"},
]


def get_schedule_documents():
    """Generate MongoDB documents for the full IPL 2026 schedule."""
    docs = []
    for m in IPL_2026_SCHEDULE:
        team1 = m["team1"]
        team2 = m["team2"]
        t1_short = TEAM_SHORT_CODES.get(team1, "")
        t2_short = TEAM_SHORT_CODES.get(team2, "")
        venue = CITY_STADIUMS.get(m["city"], m["city"])
        dt_gmt = _date_to_iso(m["date"], m["time"])

        docs.append({
            "matchId": f"ipl2026_{m['match_number']:03d}",
            "match_number": m["match_number"],
            "team1": team1,
            "team2": team2,
            "team1Short": t1_short,
            "team2Short": t2_short,
            "venue": venue,
            "city": m["city"],
            "dateTimeGMT": dt_gmt,
            "timeIST": m["time"],
            "matchType": "T20",
            "series": "TATA IPL 2026",
            "status": "Upcoming",
        })
    return docs
