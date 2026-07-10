from bs4 import BeautifulSoup

file_path = 'templates/index.html'
with open(file_path, 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f, 'html.parser')

# 1. Remove all span.select2 elements which are the fake UI
for fake_select in soup.find_all('span', class_='select2-container'):
    fake_select.decompose()

# 2. Make native select elements visible
for select in soup.find_all('select'):
    if select.has_attr('class'):
        if 'select2-hidden-accessible' in select['class']:
            select['class'].remove('select2-hidden-accessible')
        if 'hidden' in select['class']:
            select['class'].remove('hidden')
    select['style'] = 'display: block !important; width: 100%; padding: 8px; border: 1px solid #ccc;'

# 3. Remove readonly and disabled attributes from inputs and buttons
for tag in soup.find_all(['input', 'button', 'select']):
    if tag.has_attr('readonly'):
        del tag['readonly']
    if tag.has_attr('disabled'):
        del tag['disabled']

# 4. Remove hidden class from wrapping divs so sections are visible
for el in soup.find_all(class_='hidden'):
    el['class'].remove('hidden')
    
# 5. Fix form display if any issues
form = soup.find('form', id='appointment')
if form:
    form['style'] = 'display: block !important;'

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(str(soup))
print("HTML cleaned!")
