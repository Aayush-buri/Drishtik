import sys
with open('backend/app/forensics/recovery/engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('''                    if reader.size < 24:
                        if frames > 0:
                            status = "PARTIAL"''', '''                    if reader.size < 24:
                        if frames > 0 and reader.size > 0:
                            status = "PARTIAL"''')

content = content.replace('''                        if reader.size < 14:
                            if frames > 0: status = "PARTIAL"''', '''                        if reader.size < 14:
                            if frames > 0 and reader.size > 0: status = "PARTIAL"''')

with open('backend/app/forensics/recovery/engine.py', 'w', encoding='utf-8') as f:
    f.write(content)
