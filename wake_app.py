import requests
import time

# Replace with your actual Streamlit URL
APP_URL = "https://nexus-ultra-pro.streamlit.app/"

def wake_up():
    try:
        response = requests.get(APP_URL)
        if response.status_code == 200:
            print(f"Successfully pinged the app! Status: {response.status_code}")
        else:
            print(f"App might be sleeping, status code: {response.status_code}")
    except Exception as e:
        print(f"Error pinging app: {e}")

if __name__ == "__main__":
    wake_up()
