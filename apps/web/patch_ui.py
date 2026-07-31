import re
import os

path = r'components\betmind\match-modal.tsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. DialogContent shadows
content = content.replace(
    'className="max-h-[92vh] w-full overflow-y-auto border border-border bg-background p-0 shadow-2xl shadow-black/60 sm:max-w-[800px]"',
    'className="max-h-[92vh] w-full overflow-y-auto border border-border/40 bg-background p-0 shadow-[0_8px_30px_rgb(0,0,0,0.8)] ring-1 ring-white/10 sm:max-w-[800px]"'
)

# 2. Card paddings and rings
content = content.replace(
    'className="bg-surface border border-border rounded-xl p-4"',
    'className="bg-surface border border-border rounded-xl px-5 py-4 ring-1 ring-white/5"'
)
content = content.replace(
    'className="bg-surface border border-border rounded-xl overflow-hidden"',
    'className="bg-surface border border-border rounded-xl overflow-hidden ring-1 ring-white/5"'
)

# 3. AI Pills
content = content.replace(
    'className="flex items-center gap-1 text-[10px] text-subtle"',
    'className="flex items-center gap-1.5 text-[10px] bg-primary/10 backdrop-blur-md border border-primary/20 text-primary font-medium shadow-sm rounded-full px-2.5 py-1"'
)
content = content.replace(
    'className="flex items-center gap-1.5 text-[11px] text-subtle bg-muted border border-border rounded-full px-3 py-1"',
    'className="flex items-center gap-1.5 text-[11px] bg-primary/10 backdrop-blur-md border border-primary/20 text-primary font-medium shadow-sm rounded-full px-3 py-1"'
)

# 4. EV Table Micro-contrast
content = content.replace(
    "row.verdict !== 'EV+' && 'hover:bg-muted/30',",
    "row.verdict !== 'EV+' && 'hover:bg-surface-raised',"
)
content = content.replace(
    '<td className="px-4 py-3 font-semibold text-foreground">{row.label}</td>',
    '<td className={cn("px-4 py-3", selectedMarket === row.key ? "font-semibold text-foreground" : "font-medium text-foreground/60")}>{row.label}</td>'
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
