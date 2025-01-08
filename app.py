import argparse
import asyncio
import sys
from urllib.parse import urlparse
import yaml
import aiohttp
import time
from collections import defaultdict
import signal

# Endpoint Monitor
class EPM:
    def __init__(self, configPath):
        self.configPath = configPath
        self.endpoints = []
        self.domainStats = defaultdict(lambda: {'up': 0, 'total': 0})
        self.running = True

    def loadConfig(self):
        """Parsing YAML"""
        with open(self.configPath, 'r') as f:
            self.endpoints = yaml.safe_load(f)
            
        # Set default method if not specified
        for endpoint in self.endpoints:
            if 'method' not in endpoint:
                endpoint['method'] = 'GET'

    def getDomain(self, url):
        """Getting URL"""
        return urlparse(url).netloc

    async def checkEndpoint(self, session, endpoint):
        """Checking an endpoint if its UP or DOWN"""
        startTime = time.time()
        domain = self.getDomain(endpoint['url'])
        
        try:
            headers = endpoint.get('headers', {})
            data = endpoint.get('body')
            
            async with session.request(
                method=endpoint['method'],
                url=endpoint['url'],
                headers=headers,
                data=data,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                elapsed_ms = (time.time() - startTime) * 1000
                
                # Check if response is UP with parameters 2xx status and <500ms latency
                isUP = (200 <= response.status < 300 and elapsed_ms < 500)
                
                # Update statistics
                self.domainStats[domain]['total'] += 1
                if isUP:
                    self.domainStats[domain]['up'] += 1
                
        except Exception as e:
            # Any exception counts as DOWN
            self.domainStats[domain]['total'] += 1

    def printAvailability(self):
        """Print availability percentage for each domain"""
        for domain, stats in self.domainStats.items():
            if stats['total'] > 0:
                availability = round(100 * stats['up'] / stats['total'])
                print(f"{domain} has {availability}% availability percentage")

    async def monitorCycle(self):
        """Run one cycle of health checks for all endpoints"""
        async with aiohttp.ClientSession() as session:
            tasks = []
            for endpoint in self.endpoints:
                tasks.append(self.checkEndpoint(session, endpoint))
            await asyncio.gather(*tasks)
        
        self.printAvailability()

    def handleInterrupt(self, signum, frame):
        """Handle CTRL+C"""
        print("\n!!! SHUTTING DOWN !!!")
        self.running = False

    async def run(self):
        """Main monitoring loop"""
        signal.signal(signal.SIGINT, self.handleInterrupt)
        
        try:
            self.loadConfig()
            
            while self.running:
                await self.monitorCycle()
                await asyncio.sleep(15)
                
        except Exception as x:
            print(f"Error: {x}", file=sys.stderr)
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='HTTP Endpoint Health Monitor')
    parser.add_argument('config', help='Path to YAML configuration file')
    args = parser.parse_args()
    
    monitor = EPM(args.config)
    asyncio.run(monitor.run())

if __name__ == '__main__':
    main()
