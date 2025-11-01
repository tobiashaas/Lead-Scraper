import re

path = r'c:\Github\Lead-Scraper\tests\integration\test_api_export.py'
content = open(path, encoding='utf-8').read()

# Remove @pytest.mark.asyncio and async from test methods
content = re.sub(r'@pytest\.mark\.asyncio\s+async def (test_\w+)\(self,', r'def \1(self,', content)

# Remove await from client calls
content = re.sub(r'response = await client\.', r'response = client.', content)

open(path, 'w', encoding='utf-8').write(content)
print('Fixed test_api_export.py')
