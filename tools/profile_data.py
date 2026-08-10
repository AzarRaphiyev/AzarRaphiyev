"""Everything about Azar that ends up on the banner, in one place."""

HANDLE = "AzarRaphiyev"
TITLE = "profile.sh --live"

# Latin transliteration on purpose: the SVG is rendered by whatever monospace
# font the visitor's OS supplies, and "Azər Rəfiyev" loses the schwa to tofu on
# most of them.
ROWS = [
    [
        ("Subject", "Azar Rafiyev"),
        ("Role", "Full-Stack Developer"),
        ("Origin", "Baku, Azerbaijan"),
        ("Education", "MSc Cybersecurity"),
        ("Status", "Building + Learning + Shipping"),
        ("ToolChain", "VS Code · Git · GitHub · Postman"),
    ],
    [
        ("Core.Lang", "JavaScript · TypeScript · SQL"),
        ("Core.Frontend", "React · Next.js · Tailwind"),
        ("Core.Backend", "Node.js · Nest.js · Express"),
        ("Core.Database", "PostgreSQL · MongoDB · Supabase"),
        ("Core.Infra", "Vercel · Supabase · GH Actions"),
    ],
    [
        ("Grid.Mail", "raphiyev@gmail.com"),
        ("Grid.Portfolio", "raphiyev.vercel.app"),
        ("Grid.LinkedIn", "/in/azer-rafiyev"),
        ("Grid.GitHub", "@AzarRaphiyev"),
    ],
]

PALETTE = {
    "dark": {
        "bg": "#0A101F",
        "panel": "#0D1526",
        "portrait": "#A78BFA",
        "chrome": "#22D3EE",
        "accent": "#10B981",
        "text": "#C8D6E8",
        "dim": "#5A7290",
        "rule": "#1D2A42",
    },
    "light": {
        "bg": "#EEF2F9",
        "panel": "#FFFFFF",
        "portrait": "#7C3AED",
        "chrome": "#0891B2",
        "accent": "#059669",
        "text": "#243449",
        "dim": "#7C8FA8",
        "rule": "#D3DDEA",
    },
}
