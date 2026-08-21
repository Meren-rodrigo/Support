#!/usr/bin/env python3
"""
Crypto Issue Monitor Bot - Revolutionary Smart Pattern
Mimics human behavior with randomization and business hours awareness
"""

import os
import json
import time
import random
import re
from datetime import datetime, timedelta
import requests
from typing import List, Dict, Set, Optional
from difflib import SequenceMatcher

class CryptoIssueMonitor:
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
        
        self.config = self.load_config()
        self.processed_issues = self.load_processed_issues()
        self.last_check_time = self.load_last_check_time()
        self.safety_tracking = self.load_safety_tracking()
        self.daily_issues_created = self.safety_tracking.get('daily_issues_created', 0)
        self.last_date = self.safety_tracking.get('last_date', '')
        
        # Max limits per run
        self.MAX_ISSUES_PER_RUN = 2
        self.MAX_ISSUES_PER_DAY = 10
    
    def load_config(self) -> Dict:
        with open('config.json', 'r') as f:
            return json.load(f)
    
    def load_processed_issues(self) -> Set[str]:
        if os.path.exists('processed_issues.json'):
            with open('processed_issues.json', 'r') as f:
                data = json.load(f)
                return set(data.get('issues', []))
        return set()
    
    def save_processed_issues(self):
        with open('processed_issues.json', 'w') as f:
            json.dump({'issues': list(self.processed_issues)}, f, indent=2)
    
    def load_last_check_time(self) -> Dict:
        if os.path.exists('last_check_time.json'):
            with open('last_check_time.json', 'r') as f:
                return json.load(f)
        return {'last_check': None, 'checks_today': 0}
    
    def save_last_check_time(self):
        with open('last_check_time.json', 'w') as f:
            json.dump(self.last_check_time, f, indent=2)
    
    def load_safety_tracking(self) -> Dict:
        if os.path.exists('safety_tracking.json'):
            with open('safety_tracking.json', 'r') as f:
                return json.load(f)
        return {'daily_issues_created': 0, 'last_date': ''}
    
    def save_safety_tracking(self):
        with open('safety_tracking.json', 'w') as f:
            json.dump(self.safety_tracking, f, indent=2)
    
    def can_create_issue(self) -> bool:
        today = datetime.utcnow().strftime('%Y-%m-%d')
        if self.last_date != today:
            self.daily_issues_created = 0
            self.last_date = today
            self.safety_tracking['daily_issues_created'] = 0
            self.safety_tracking['last_date'] = today
            self.save_safety_tracking()
        return self.daily_issues_created < self.MAX_ISSUES_PER_DAY
    
    def is_business_hours(self) -> bool:
        now = datetime.utcnow()
        hour = now.hour
        return 8 <= hour <= 22
    
    def matches_criteria(self, issue: Dict) -> bool:
        title = issue.get('title', '').lower()
        body = issue.get('body', '') or ''
        body = body.lower()
        content = f"{title} {body}"
        
        keywords = self.config.get('keywords', [])
        found_count = 0
        for keyword in keywords:
            if keyword.lower() in content:
                found_count += 1
        
        return found_count >= 2
    
    def create_issue_in_target_repo(self, source_issue: Dict, source_repo: str) -> bool:
        title = source_issue.get('title', '')
        body = source_issue.get('body', '') or ''
        issue_number = source_issue.get('number', 0)
        issue_url = f"https://github.com/{source_repo}/issues/{issue_number}"
        
        new_title = f"[{source_repo}] {title[:80]}"
        
        random_templates = [
            f"This issue has been found in {source_repo}.\n\n**Original Report:** {issue_url}\n\n{body[:2000]}",
            f"A matching issue was detected in {source_repo}.\n\n**Source:** {issue_url}\n\n{body[:2000]}",
            f"Related issue from {source_repo}:\n\n**Link:** {issue_url}\n\n{body[:2000]}"
        ]
        new_body = random.choice(random_templates)
        
        url = f'https://api.github.com/repos/{self.target_repo}/issues'
        payload = {'title': new_title, 'body': new_body}
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            if response.status_code == 201:
                print(f"   ✅ Created issue #{response.json()['number']}")
                self.daily_issues_created += 1
                self.safety_tracking['daily_issues_created'] = self.daily_issues_created
                self.safety_tracking['last_date'] = self.last_date
                self.save_safety_tracking()
                return True
            return False
        except Exception as e:
            print(f"   ⚠️  Error creating issue: {str(e)}")
            return False
    
    def monitor_repositories(self):
        print(f"\n{'='*60}")
        print(f"🔍 Crypto Issue Monitor - Smart Pattern")
        print(f"⏰ {datetime.utcnow().isoformat()}")
        print(f"{'='*60}\n")
        
        # Reset daily counter if new day
        today = datetime.utcnow().strftime('%Y-%m-%d')
        if self.last_date != today:
            self.daily_issues_created = 0
            self.last_date = today
        
        # Check daily limit
        if self.daily_issues_created >= self.MAX_ISSUES_PER_DAY:
            print(f"⚠️  Daily limit ({self.MAX_ISSUES_PER_DAY}) reached. Skipping.")
            return
        
        repos = self.config.get('monitored_repos', [])
        total_issues_found = 0
        total_issues_created = 0
        
        for repo in repos:
            if total_issues_created >= self.MAX_ISSUES_PER_RUN:
                break
            if not self.can_create_issue():
                break
            
            print(f"\n📂 Checking: {repo}")
            url = f'https://api.github.com/repos/{repo}/issues'
            params = {'state': 'open', 'per_page': 30, 'sort': 'created', 'direction': 'desc'}
            
            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=15)
                if response.status_code != 200:
                    print(f"   ⚠️  HTTP {response.status_code}")
                    continue
                
                issues = response.json()
                if not issues:
                    print(f"   📭 No open issues")
                    continue
                
                for issue in issues:
                    if total_issues_created >= self.MAX_ISSUES_PER_RUN:
                        break
                    if not self.can_create_issue():
                        break
                    
                    issue_id = f"{repo}#{issue['number']}"
                    
                    if issue_id in self.processed_issues:
                        continue
                    
                    if self.matches_criteria(issue):
                        total_issues_found += 1
                        print(f"   ✅ Match: #{issue['number']} - {issue['title'][:35]}")
                        
                        # 10% random skip
                        if random.random() < 0.10:
                            print(f"   🎭 Skipping (random choice)")
                            self.processed_issues.add(issue_id)
                            continue
                        
                        if not self.can_create_issue():
                            break
                        
                        created = self.create_issue_in_target_repo(issue, repo)
                        if created:
                            total_issues_created += 1
                            self.processed_issues.add(issue_id)
                    else:
                        self.processed_issues.add(issue_id)
            
            except Exception as e:
                print(f"   ❌ Error: {str(e)}")
                continue
            
            # Random delay between repos
            if repos.index(repo) < len(repos) - 1:
                delay = random.uniform(2, 5)
                time.sleep(delay)
        
        self.save_processed_issues()
        self.save_last_check_time()
        
        print(f"\n{'='*60}")
        print(f"📊 Summary:")
        print(f"   - Found: {total_issues_found}")
        print(f"   - Created: {total_issues_created}/{self.MAX_ISSUES_PER_RUN}")
        print(f"   - Daily: {self.daily_issues_created}/{self.MAX_ISSUES_PER_DAY}")
        print(f"{'='*60}\n")

def main():
    try:
        monitor = CryptoIssueMonitor()
        monitor.monitor_repositories()
        print("✅ Done\n")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise

if __name__ == '__main__':
    main()
