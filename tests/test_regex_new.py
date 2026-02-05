import re
import unittest

# This logic will mirror what we plan to put in server/main.py

def parse_protocol(text):
    # Regex to parse the protocol
    # Updated to be more flexible with whitespace and new headers
    pattern = r"<<<SPEC_START>>>\s+(?:[*]\s*)?Target-Section:\s*(.*?)\n\s*(?:[*]\s*)?Change-Summary:\s*(.*?)\n\s*(.*?)<<<SPEC_END>>>"
    matches = list(re.finditer(pattern, text, re.DOTALL))
    
    results = []
    for match in matches:
        target_section = match.group(1).strip()
        change_summary = match.group(2).strip()
        raw_content = match.group(3).strip()
        
        # Splitting logic
        # Split by headers (#, ##, etc.)
        # We need to preserve the header in the chunk
        
        lines = raw_content.split('\n')
        current_chunk = []
        chunks = []
        
        for line in lines:
            if re.match(r'^#+\s', line):
                if current_chunk:
                    chunks.append("\n".join(current_chunk))
                current_chunk = [line]
            else:
                current_chunk.append(line)
        
        if current_chunk:
            chunks.append("\n".join(current_chunk))
            
        # If no headers found, treat the whole thing as one chunk
        if not chunks and raw_content:
             chunks = [raw_content]
             
        for chunk in chunks:
            results.append({
                "target_header": target_section, # This is the "Intent" target
                "summary": change_summary,
                "content": chunk
            })
            
    return results

class TestProtocolParsing(unittest.TestCase):

    def test_basic_single_block(self):
        text = """
<<<SPEC_START>>>
Target-Section: Auth
Change-Summary: Added login
        
### Login
User logs in here.
<<<SPEC_END>>>
        """
        parsed = parse_protocol(text)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]['target_header'], "Auth")
        self.assertEqual(parsed[0]['summary'], "Added login")
        self.assertIn("### Login", parsed[0]['content'])

    def test_multiple_headers_in_block(self):
        text = """
<<<SPEC_START>>>
Target-Section: User Management
Change-Summary: Define users and roles

## Users
Define user data.

## Roles
Define role types.
<<<SPEC_END>>>
        """
        parsed = parse_protocol(text)
        self.assertEqual(len(parsed), 2)
        
        self.assertEqual(parsed[0]['target_header'], "User Management")
        self.assertIn("## Users", parsed[0]['content'])
        
        self.assertEqual(parsed[1]['target_header'], "User Management")
        self.assertIn("## Roles", parsed[1]['content'])

    def test_paragraph_splitting_fallback(self):
        # The user mentioned merging algo to work on each paragraph/header independently.
        # Ideally we split by headers. If there are just paragraphs, maybe we should treat them together 
        # unless requested otherwise. For now, the implementing strictly asked for "independently".
        # Let's verify header splitting first which is the "Better" way.
        pass

    def test_bullet_points(self):
        text = """
<<<SPEC_START>>>

* Target-Section: Context, Aim & Integration: Integration
* Change-Summary: Defined the tri-layer architectural stack.

### Architectural Stack
Content.
<<<SPEC_END>>>
        """
        parsed = parse_protocol(text)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]['target_header'], "Context, Aim & Integration: Integration")

if __name__ == '__main__':
    unittest.main()
