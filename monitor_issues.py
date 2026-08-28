#!/usr/bin/env python3
"""
Crypto Issue Monitor Bot - Revolutionary Smart Pattern
Mimics human behavior with randomization and business hours awareness
"""

import os
import json
import time
import random
from datetime import datetime, timezone
import requests
from typing import Dict, Set

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
        self.safety_tracking = self.load_safety_tracking()
        self.daily_issues_created = self.safety_tracking.get('daily_issues_created', 0)
        self.last_date = self.safety_tracking.get('last_date', '')

        # Limits
        self.MAX_ISSUES_PER_DAY = 10
        self.MAX_ISSUES_PER_RUN = 10

    # ---------- config / state ----------

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

    def load_safety_tracking(self) -> Dict:
        if os.path.exists('safety_tracking.json'):
            with open('safety_tracking.json', 'r') as f:
                return json.load(f)
        return {'daily_issues_created': 0, 'last_date': ''}

    def save_safety_tracking(self):
        with open('safety_tracking.json', 'w') as f:
            json.dump(self.safety_tracking, f, indent=2)

    # ---------- daily counter ----------

    def reset_daily_counter_if_new_day(self):
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        if self.last_date != today:
            self.daily_issues_created = 0
            self.last_date = today
            self.safety_tracking['daily_issues_created'] = 0
            self.safety_tracking['last_date'] = today
            self.save_safety_tracking()

    def can_create_issue(self) -> bool:
        self.reset_daily_counter_if_new_day()
        return self.daily_issues_created < self.MAX_ISSUES_PER_DAY

    def is_business_hours(self) -> bool:
        now = datetime.now(timezone.utc)
        return 8 <= now.hour <= 22

    # ---------- matching ----------

    def matches_criteria(self, issue: Dict) -> bool:
        title = (issue.get('title') or '').lower()
        body = (issue.get('body') or '').lower()
        content = f"{title} {body}"

        keywords = self.config.get('keywords', [])
        found_count = sum(1 for keyword in keywords if keyword.lower() in content)

        return found_count >= 2

    # ---------- issue creation ----------

    def create_issue_in_target_repo(self, source_issue: Dict, source_repo: str) -> bool:
        title = source_issue.get('title', '')
        body = source_issue.get('body', '') or ''
        issue_number = source_issue.get('number', 0)
        issue_url = f"https://github.com/{source_repo}/issues/{issue_number}"
        author = source_issue.get('user', {}).get('login', 'unknown')

        new_body = (
            f"{title}\n\n"
            f"{body[:2000]}\n\n"
            f"---\n"
            f"*Reported by @{author} | Source: [{source_repo}#{issue_number}]({issue_url})*"
        )

        url = f'https://api.github.com/repos/{self.target_repo}/issues'
        payload = {'title': title, 'body': new_body}

        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            if response.status_code == 201:
                created_number = response.json().get('number')
                print(f"   ✅ Created issue #{created_number}")

                self.daily_issues_created += 1
                self.safety_tracking['daily_issues_created'] = self.daily_issues_created
                self.safety_tracking['last_date'] = self.last_date
                self.save_safety_tracking()
                return True

            print(f"   ⚠️  Failed to create issue: HTTP {response.status_code} - {response.text[:200]}")
            return False
        except Exception as e:
            print(f"   ⚠️  Error creating issue: {str(e)}")
            return False

    # ---------- monitoring ----------

    def fetch_issues(self, repo: str) -> list:
        """Fetch up to 2 pages (60 issues) of newest open issues, excluding PRs."""
        all_issues = []
        for page in (1, 2):
            url = f'https://api.github.com/repos/{repo}/issues'
            params = {
                'state': 'open',
                'per_page': 30,
                'page': page,
                'sort': 'created',
                'direction': 'desc',
            }
            response = requests.get(url, headers=self.headers, params=params, timeout=15)
            if response.status_code != 200:
                print(f"   ⚠️  HTTP {response.status_code}")
                break
            issues = response.json()
            if not issues:
                break
            all_issues.extend(issues)
            if len(issues) < 30:
                break
        # Filter out pull requests (GitHub returns PRs from the issues endpoint)
        return [i for i in all_issues if 'pull_request' not in i]

    def monitor_repositories(self):
        print(f"\n{'='*60}")
        print(f"🔍 Crypto Issue Monitor - Smart Pattern")
        print(f"⏰ {datetime.now(timezone.utc).isoformat()}")
        print(f"{'='*60}\n")

        self.reset_daily_counter_if_new_day()

        if self.daily_issues_created >= self.MAX_ISSUES_PER_DAY:
            print(f"⚠️  Daily limit ({self.MAX_ISSUES_PER_DAY}) reached. Skipping.")
            return

        if not self.is_business_hours():
            print("🌙 Outside business hours (UTC 08-22). Skipping.")
            return

        repos = self.config.get('monitored_repos', [])
        total_issues_found = 0
        total_issues_created = 0
        state_dirty = False

        for repo_index, repo in enumerate(repos):
            if total_issues_created >= self.MAX_ISSUES_PER_RUN:
                break
            if not self.can_create_issue():
                break

            print(f"\n📂 Checking: {repo}")

            try:
                issues = self.fetch_issues(repo)
                if not issues:
                    print("   📭 No open issues")

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
                        print(f"   ✅ Match: #{issue['number']} - {(issue.get('title') or '')[:35]}")

                        # 10% random skip (human-like behavior)
                        if random.random() < 0.10:
                            print("   🎭 Skipping (random choice)")
                            self.processed_issues.add(issue_id)
                            state_dirty = True
                            continue

                        created = self.create_issue_in_target_repo(issue, repo)
                        # Mark as processed regardless of outcome so we don't
                        # retry a failing issue forever
                        self.processed_issues.add(issue_id)
                        state_dirty = True

                        if created:
                            total_issues_created += 1
                            # Save state incrementally so a crash doesn't
                            # cause duplicate mirrored issues
                            self.save_processed_issues()
                    else:
                        self.processed_issues.add(issue_id)
                        state_dirty = True

            except Exception as e:
                print(f"   ❌ Error: {str(e)}")
                continue

            # Random delay between repos
            if repo_index < len(repos) - 1:
                time.sleep(random.uniform(2, 5))

        if state_dirty:
            self.save_processed_issues()

        print(f"\n{'='*60}")
        print(f"📊 Summary:")
        print(f"   - Found: {total_issues_found}")
        print(f"   - Created: {total_issues_created}")
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
