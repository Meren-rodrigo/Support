#!/usr/bin/env python3
"""
Auto-Responder Bot - UPGRADED VERSION
Automatically responds to auto-detected issues with intelligent detection
"""

import os
import json
import requests
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Set

class IssueResponderBot:
    def __init__(self):
        self.github_token = os.environ.get('GITHUB_TOKEN')
        if not self.github_token:
            raise ValueError("GITHUB_TOKEN environment variable not set")
        
        self.headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        self.target_repo = os.environ.get('TARGET_REPO')
        if not self.target_repo:
            raise ValueError("TARGET_REPO environment variable not set")
        
        print(f"📦 Target repo: {self.target_repo}")
        self.load_responses()
        self.responded_issues = self.load_responded_issues()
    
    def load_responses(self):
        """Load bot response templates"""
        if not os.path.exists('bot_responses.json'):
            print("⚠️  bot_responses.json not found, creating default")
            self.responses = {
                "general": "Thank you for your report. Our team will review this shortly."
            }
            return
        with open('bot_responses.json', 'r') as f:
            self.responses = json.load(f)
        print(f"✅ Loaded {len(self.responses)} response templates")
    
    def load_responded_issues(self) -> Set[int]:
        """Load list of already responded issues"""
        if os.path.exists('responded_issues.json'):
            with open('responded_issues.json', 'r') as f:
                data = json.load(f)
                return set(data.get('issues', []))
        print("📭 No previous responded issues found, starting fresh")
        return set()
    
    def save_responded_issues(self):
        """Save responded issues to file"""
        with open('responded_issues.json', 'w') as f:
            json.dump({'issues': list(self.responded_issues)}, f, indent=2)
    
    def check_rate_limit(self):
        """Check GitHub API rate limit"""
        response = requests.get('https://api.github.com/rate_limit', headers=self.headers)
        if response.status_code == 200:
            data = response.json()
            remaining = data['rate']['remaining']
            reset_time = datetime.fromtimestamp(data['rate']['reset'])
            print(f"📊 API: {remaining} requests (resets {reset_time.strftime('%H:%M')})")
            return remaining
        return 0
    
    def get_unresponded_issues(self) -> List[Dict]:
        """Get issues that haven't been responded to"""
        url = f'https://api.github.com/repos/{self.target_repo}/issues'
        params = {'state': 'open', 'per_page': 30, 'sort': 'created', 'direction': 'desc'}
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            if response.status_code == 200:
                issues = response.json()
                unresponded = []
                for issue in issues:
                    issue_num = issue['number']
                    if issue_num in self.responded_issues:
                        continue
                    if not self.has_bot_comment(issue_num):
                        unresponded.append(issue)
                return unresponded
            else:
                print(f"⚠️  GitHub API returned {response.status_code}: {response.text[:200]}")
                return []
        except Exception as e:
            print(f"⚠️  Error fetching issues: {str(e)}")
            return []
    
    def has_bot_comment(self, issue_number: int) -> bool:
        """Check if issue already has a bot comment"""
        url = f'https://api.github.com/repos/{self.target_repo}/issues/{issue_number}/comments'
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                comments = response.json()
                for comment in comments:
                    comment_body = comment.get('body', '')
                    commenter = comment.get('user', {}).get('login', '')
                    
                    if commenter == 'github-actions[bot]':
                        return True
                    
                    signatures = [
                        'Our support team has been notified',
                        'Our support team has received',
                        'Our support team will',
                        'Our development team will',
                        'Thank you for reporting',
                        'Thank you for bringing this to our attention',
                        'Thank you for reaching out',
                        'Thank you for submitting',
                        'Support Portal',
                        'Need immediate assistance?',
                        'Contact our security team:',
                        'Contact our team:',
                        'Contact us:'
                    ]
                    
                    if any(sig in comment_body for sig in signatures):
                        return True
            return False
        except Exception as e:
            print(f"⚠️  Error checking comments for #{issue_number}: {str(e)}")
            return False
    
    def detect_issue_category(self, issue: Dict) -> str:
        """Detect the category of the issue based on labels and keywords"""
        labels = [label['name'].lower() for label in issue.get('labels', [])]
        
        label_mapping = {
            'security': 'security',
            'bug': 'bug',
            'transaction': 'transaction',
            'wallet': 'wallet',
            'contract': 'contract',
            'gas-fee': 'gas',
            'help': 'help'
        }
        
        for label in labels:
            if label in label_mapping:
                return label_mapping[label]
        
        title = issue.get('title', '').lower()
        body = issue.get('body', '') or ''
        body = body.lower()
        content = f"{title} {body}"
        
        categories = {
            'security': ['security', 'vulnerability', 'exploit', 'hack', 'attack', 'breach', 'malicious'],
            'bug': ['bug', 'error', 'broken', 'not working', 'failed', 'crash', 'issue', 'problem'],
            'transaction': ['transaction', 'swap', 'transfer', 'send', 'receive', 'stuck', 'pending', 'tx'],
            'wallet': ['wallet', 'balance', 'account', 'address', 'missing', 'disappeared', 'metamask', 'ledger'],
            'contract': ['contract', 'smart contract', 'deploy', 'solidity', 'web3'],
            'gas': ['gas', 'fee', 'cost', 'expensive', 'high fee'],
            'token': ['token', 'nft', 'erc20', 'erc721', 'coin'],
            'help': ['help', 'how to', 'question', 'confused', 'unclear', 'guide']
        }
        
        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword in content:
                    return category
        
        return 'general'
    
    def post_response(self, issue_number: int, response_text: str):
        """Post a comment response to an issue"""
        url = f'https://api.github.com/repos/{self.target_repo}/issues/{issue_number}/comments'
        payload = {'body': response_text}
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            if response.status_code == 201:
                print(f"✅ Responded to issue #{issue_number}")
                self.responded_issues.add(issue_number)
                self.save_responded_issues()
                return True
            else:
                print(f"⚠️  Failed to post comment to #{issue_number}: {response.status_code} - {response.text[:200]}")
                return False
        except Exception as e:
            print(f"⚠️  Exception posting comment to #{issue_number}: {str(e)}")
            return False
    
    def respond_to_issues(self):
        """Main function to respond to issues"""
        print(f"\n{'='*60}")
        print(f"🤖 Auto-Responder Bot")
        print(f"⏰ {datetime.utcnow().isoformat()}")
        print(f"{'='*60}\n")
        
        remaining = self.check_rate_limit()
        if remaining < 50:
            print("⚠️  Low API limit - skipping run")
            return
        
        issues = self.get_unresponded_issues()
        
        if not issues:
            print("📭 No new issues to respond to")
            print(f"✅ Done\n")
            return
        
        print(f"📬 Found {len(issues)} issue(s) to respond to\n")
        
        responded_count = 0
        for issue in issues:
            category = self.detect_issue_category(issue)
            print(f"📝 Issue #{issue['number']}: {issue['title'][:50]}...")
            print(f"   📂 Category: {category}")
            
            template = self.responses.get(category, self.responses.get('general'))
            
            if not template:
                print(f"   ⚠️  No template for category '{category}' - using general")
                template = self.responses.get('general', 'Thank you for your report. Our team will review this shortly.')
            
            if self.post_response(issue['number'], template):
                responded_count += 1
        
        print(f"\n{'='*60}")
        print(f"✅ Responded to {responded_count}/{len(issues)} issues")
        print(f"{'='*60}\n")

def main():
    try:
        bot = IssueResponderBot()
        bot.respond_to_issues()
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
