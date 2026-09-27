import sys
with open('backend/app/forensics/recovery/engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix DHAV
content = content.replace('''                    if reader.size < 24:
                        if frames > 0:
                            status = "PARTIAL"
                        break''', '''                    if reader.size < 24:
                        if frames > 0:
                            status = "PARTIAL"
                        if frames == 0:
                            reader.advance(reader.size)
                        break''')

# Fix Hikvision
content = content.replace('''                        if reader.size < 14:
                            if frames > 0: status = "PARTIAL"
                            break''', '''                        if reader.size < 14:
                            if frames > 0: status = "PARTIAL"
                            if frames == 0: reader.advance(reader.size)
                            break''')

# Fix MP4
content = content.replace('''                        if reader.size < 8:
                            break''', '''                        if reader.size < 8:
                            if current_cand_len == 0: reader.advance(reader.size)
                            break''')

with open('backend/app/forensics/recovery/engine.py', 'w', encoding='utf-8') as f:
    f.write(content)
