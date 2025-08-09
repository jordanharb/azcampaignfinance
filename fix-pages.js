const fs = require('fs');
const path = require('path');

// Files to fix
const files = [
  'app/page.tsx',
  'app/not-found.tsx',
  'app/candidate/[id]/page.tsx',
  'app/bulk/page.tsx'
];

files.forEach(file => {
  const filePath = path.join(__dirname, file);
  
  if (fs.existsSync(filePath)) {
    let content = fs.readFileSync(filePath, 'utf8');
    
    // Remove event handler lines and their surrounding empty blocks
    content = content.replace(/\s*onMouseOver=\{[^}]*\}/g, '');
    content = content.replace(/\s*onMouseOut=\{[^}]*\}/g, '');
    content = content.replace(/\s*onFocus=\{[^}]*\}/g, '');
    content = content.replace(/\s*onBlur=\{[^}]*\}/g, '');
    
    // Clean up any broken syntax from partial deletions
    content = content.replace(/\s+e\.target\.style\.[^}]+\}\}/g, '');
    content = content.replace(/\s+e\.currentTarget\.style\.[^}]+\}\}/g, '');
    content = content.replace(/\s+\}\}/g, '');
    
    fs.writeFileSync(filePath, content, 'utf8');
    console.log(`Fixed ${file}`);
  }
});