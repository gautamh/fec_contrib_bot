# https://claude.ai/chat/230fd208-927f-4f7e-b646-9d96c72c542e

import os
import requests
from datetime import datetime, timedelta
from typing import List, Dict
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass
from google.cloud import secretmanager
import functions_framework
from flask import Request

@dataclass
class Contributor:
    name: str
    employer: str = None
    
@dataclass
class Contribution:
    date: datetime
    amount: float
    contributor_name: str
    employer: str
    committee_name: str
    load_date: datetime

def get_secret(secret_id: str) -> str:
    """Retrieve secret from Google Cloud Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{os.environ['PROJECT_ID']}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

def get_fec_contributions(contributor: Contributor, api_key: str, days_back_load: int = 14, days_back_contrib: int = 180) -> List[Contribution]:
    """
    Fetch contributions from FEC API for a given contributor.
    
    Args:
        contributor: Contributor object containing name and employer
        api_key: FEC API key
        days_back_load: Number of days back to check for load_date
        days_back_contrib: Number of days back to search for contributions
    """
    base_url = "https://api.open.fec.gov/v1/schedules/schedule_a/"
    
    # Calculate date ranges
    end_date = datetime.now()
    contrib_start_date = end_date - timedelta(days=days_back_contrib)
    min_load_date = end_date - timedelta(days=days_back_load)
    
    params = {
        'api_key': api_key,
        'contributor_name': contributor.name,
        'contributor_employer': contributor.employer,
        'min_date': contrib_start_date.strftime('%m/%d/%Y'),
        'max_date': end_date.strftime('%m/%d/%Y'),
        'sort': '-contribution_receipt_date',
        'per_page': 100,
        'is_individual': True
    }
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        contributions = []
        for result in data['results']:
            # Parse the load_date
            load_date = datetime.strptime(result['load_date'], '%Y-%m-%dT%H:%M:%S')
            
            # Only include contributions loaded after min_load_date
            if load_date > min_load_date:
                contribution = Contribution(
                    date=datetime.strptime(result['contribution_receipt_date'], '%Y-%m-%d'),
                    amount=float(result['contribution_receipt_amount']),
                    contributor_name=result['contributor_name'],
                    employer=result['contributor_employer'] or 'Not reported',
                    committee_name=result['committee']['name'],
                    load_date=load_date
                )
                contributions.append(contribution)
        
        return contributions
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching FEC data for {contributor.name}: {str(e)}")
        return []

def format_email_body(contributions_by_contributor: Dict[str, List[Contribution]]) -> str:
    """Format contribution data into an HTML email body."""
    html = "<html><body>"
    html += "<h2>FEC Contribution Alert</h2>"
    
    for contributor, contributions in contributions_by_contributor.items():
        if contributions:
            html += f"<h3>Contributions from {contributor}</h3>"
            html += "<table border='1' style='border-collapse: collapse; width: 100%;'>"
            html += "<tr><th>Date</th><th>Amount</th><th>Committee</th><th>Employer</th></tr>"
            
            for contribution in contributions:
                html += f"""
                <tr>
                    <td>{contribution.date.strftime('%Y-%m-%d')}</td>
                    <td>${contribution.amount:,.2f}</td>
                    <td>{contribution.committee_name}</td>
                    <td>{contribution.employer}</td>
                    <td>{contribution.load_date.strftime('%Y-%m-%d %H:%M:%S')}</td>
                </tr>
                """
            html += "</table><br>"
        else:
            html += f"<p>No recent contributions found for {contributor}</p><br>"
    
    html += "</body></html>"
    return html

def send_email(to_email: str, subject: str, html_content: str, smtp_config: dict):
    """Send an HTML email using SMTP."""
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = smtp_config['from_email']
    msg['To'] = to_email
    
    html_part = MIMEText(html_content, 'html')
    msg.attach(html_part)
    
    try:
        with smtplib.SMTP(smtp_config['server'], smtp_config['port']) as server:
            server.starttls()
            server.login(smtp_config['username'], smtp_config['password'])
            server.send_message(msg)
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        raise

@functions_framework.http
def monitor_contributions(request: Request):
    """Cloud Function entry point to monitor FEC contributions."""
    try:
        # Get configuration from environment variables and secrets
        project_id = os.environ['PROJECT_ID']
        notification_email = os.environ['NOTIFICATION_EMAIL']
        
        # Get secrets
        fec_api_key = get_secret('fec-api-key')
        smtp_password = get_secret('smtp-password')
        
        # SMTP configuration
        smtp_config = {
            'server': os.environ.get('SMTP_SERVER', 'smtp.gmail.com'),
            'port': int(os.environ.get('SMTP_PORT', '587')),
            'username': os.environ.get('SMTP_USERNAME'),
            'password': smtp_password,
            'from_email': os.environ.get('FROM_EMAIL')
        }
        
        # List of contributors to monitor
        contributors = [
            Contributor(
                name="Sundar Pichai",
                employer="Google"),
            Contributor(
                name="Kent Walker",
                employer="Google"),
            Contributor(
                name="Thomas Kurian",
                employer="Google"),
            Contributor(
                name="Jen Fitzpatrick",
                employer="Google"),
            Contributor(
                name="Rick Osterloh",
                employer="Google"),
            Contributor(
                name="Prabhakar Raghavan",
                employer="Google"),
            Contributor(
                name="Lorraine Twohill",
                employer="Google"),
            Contributor(
                name="Corey DuBrowa",
                employer="Google"),
            Contributor(
                name="Neal Mohan",
                employer="Google"),
            Contributor(
                name="Anat Ashkenazi",
                employer="Google"),
            Contributor(
                name="Jeff Dean",
                employer="Google"),
            Contributor(
                name="Ruth Porat",
                employer="Google"),
            # Add more contributors as needed
        ]
        
        # Fetch contributions for each contributor
        contributions_by_contributor = {}
        for contributor in contributors:
            contributions = get_fec_contributions(contributor, fec_api_key)
            contributions_by_contributor[contributor.name] = contributions
        
        # Format and send email if there are any contributions
        if any(contributions_by_contributor.values()):
            html_content = format_email_body(contributions_by_contributor)
            subject = f"FEC Contribution Alert - {datetime.now().strftime('%Y-%m-%d')}"
            send_email(notification_email, subject, html_content, smtp_config)
            return "Alert sent successfully", 200
        else:
            return "No new contributions found", 200
            
    except Exception as e:
        print(f"Error in monitor_contributions: {str(e)}")
        return f"Error: {str(e)}", 500

