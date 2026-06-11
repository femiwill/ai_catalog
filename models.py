from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


tool_categories = db.Table(
    "tool_categories",
    db.Column("tool_id", db.Integer, db.ForeignKey("tools.id"), primary_key=True),
    db.Column(
        "category_id", db.Integer, db.ForeignKey("categories.id"), primary_key=True
    ),
)


class Company(db.Model):
    __tablename__ = "companies"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    slug = db.Column(db.String(120), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    website = db.Column(db.String(255))
    founded = db.Column(db.String(20))
    hq = db.Column(db.String(120))
    tools = db.relationship(
        "Tool", backref="company", lazy="select", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "website": self.website,
            "founded": self.founded,
            "hq": self.hq,
            "tool_count": len(self.tools),
        }


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    slug = db.Column(db.String(120), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))
    sort_order = db.Column(db.Integer, default=100)

    @property
    def tool_count(self):
        return len(self.tools)


class Tool(db.Model):
    __tablename__ = "tools"
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(160), nullable=False, unique=True, index=True)
    tagline = db.Column(db.String(255))
    description = db.Column(db.Text)
    pricing_model = db.Column(db.String(60))  # Free, Freemium, Paid, Enterprise
    pricing_details = db.Column(db.String(255))
    strengths = db.Column(db.Text)
    weaknesses = db.Column(db.Text)
    best_for = db.Column(db.Text)
    website = db.Column(db.String(255))
    launched = db.Column(db.String(20))
    featured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    categories = db.relationship(
        "Category", secondary=tool_categories, backref="tools", lazy="select"
    )

    def strengths_list(self):
        return [s.strip() for s in (self.strengths or "").split("|") if s.strip()]

    def weaknesses_list(self):
        return [w.strip() for w in (self.weaknesses or "").split("|") if w.strip()]

    def best_for_list(self):
        return [b.strip() for b in (self.best_for or "").split("|") if b.strip()]


PRICING_MODELS = ["Free", "Freemium", "Paid", "Enterprise"]
