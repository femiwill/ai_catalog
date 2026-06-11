from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    abort,
)
from sqlalchemy import or_, func
from config import Config
from models import db, Company, Category, Tool, PRICING_MODELS
import re

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)


def slugify(text):
    text = re.sub(r"[^\w\s-]", "", (text or "").lower())
    return re.sub(r"[\s_-]+", "-", text).strip("-")


@app.context_processor
def inject_globals():
    return {
        "site_name": app.config["SITE_NAME"],
        "site_tagline": app.config["SITE_TAGLINE"],
        "pricing_models": PRICING_MODELS,
    }


@app.route("/")
def home():
    featured = (
        Tool.query.filter_by(featured=True).order_by(Tool.name).limit(12).all()
    )
    categories = Category.query.order_by(Category.sort_order, Category.name).all()
    total_tools = db.session.query(func.count(Tool.id)).scalar() or 0
    total_companies = db.session.query(func.count(Company.id)).scalar() or 0
    return render_template(
        "home.html",
        featured=featured,
        categories=categories,
        total_tools=total_tools,
        total_companies=total_companies,
    )


@app.route("/categories")
def categories():
    cats = Category.query.order_by(Category.sort_order, Category.name).all()
    return render_template("categories.html", categories=cats)


@app.route("/categories/<slug>")
def category_detail(slug):
    cat = Category.query.filter_by(slug=slug).first_or_404()
    tools = sorted(cat.tools, key=lambda t: t.name.lower())
    return render_template("category.html", category=cat, tools=tools)


@app.route("/companies")
def companies():
    comps = Company.query.order_by(Company.name).all()
    return render_template("companies.html", companies=comps)


@app.route("/companies/<slug>")
def company_detail(slug):
    comp = Company.query.filter_by(slug=slug).first_or_404()
    tools = sorted(comp.tools, key=lambda t: t.name.lower())
    return render_template("company.html", company=comp, tools=tools)


@app.route("/tools/<slug>")
def tool_detail(slug):
    tool = Tool.query.filter_by(slug=slug).first_or_404()
    related = (
        Tool.query.join(Tool.categories)
        .filter(Category.id.in_([c.id for c in tool.categories]))
        .filter(Tool.id != tool.id)
        .distinct()
        .limit(8)
        .all()
    )
    return render_template("tool.html", tool=tool, related=related)


@app.route("/search")
def search():
    q = (request.args.get("q") or "").strip()
    pricing = request.args.get("pricing") or ""
    category_slug = request.args.get("category") or ""
    company_slug = request.args.get("company") or ""

    query = Tool.query
    if q:
        like = f"%{q}%"
        query = query.join(Company).filter(
            or_(
                Tool.name.ilike(like),
                Tool.tagline.ilike(like),
                Tool.description.ilike(like),
                Tool.best_for.ilike(like),
                Company.name.ilike(like),
            )
        )
    if pricing:
        query = query.filter(Tool.pricing_model == pricing)
    if category_slug:
        query = query.join(Tool.categories).filter(Category.slug == category_slug)
    if company_slug:
        if not q:
            query = query.join(Company)
        query = query.filter(Company.slug == company_slug)

    results = query.order_by(Tool.name).all()
    all_categories = Category.query.order_by(Category.name).all()
    all_companies = Company.query.order_by(Company.name).all()
    return render_template(
        "search.html",
        q=q,
        pricing=pricing,
        category_slug=category_slug,
        company_slug=company_slug,
        results=results,
        all_categories=all_categories,
        all_companies=all_companies,
    )


@app.route("/about")
def about():
    return render_template("about.html")


# ---------------- Admin ----------------


def admin_required():
    if not session.get("admin"):
        return False
    return True


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == app.config["ADMIN_PASSWORD"]:
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Wrong password", "error")
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("home"))


@app.route("/admin")
def admin_dashboard():
    if not admin_required():
        return redirect(url_for("admin_login"))
    tools = Tool.query.order_by(Tool.created_at.desc()).all()
    companies = Company.query.order_by(Company.name).all()
    categories = Category.query.order_by(Category.name).all()
    return render_template(
        "admin/dashboard.html",
        tools=tools,
        companies=companies,
        categories=categories,
    )


@app.route("/admin/tools/new", methods=["GET", "POST"])
@app.route("/admin/tools/<int:tool_id>/edit", methods=["GET", "POST"])
def admin_tool_form(tool_id=None):
    if not admin_required():
        return redirect(url_for("admin_login"))
    tool = Tool.query.get(tool_id) if tool_id else None
    companies = Company.query.order_by(Company.name).all()
    categories = Category.query.order_by(Category.name).all()

    if request.method == "POST":
        if tool is None:
            tool = Tool()
        tool.name = request.form.get("name", "").strip()
        tool.slug = slugify(request.form.get("slug") or tool.name)
        tool.company_id = int(request.form["company_id"])
        tool.tagline = request.form.get("tagline", "").strip()
        tool.description = request.form.get("description", "").strip()
        tool.pricing_model = request.form.get("pricing_model", "").strip()
        tool.pricing_details = request.form.get("pricing_details", "").strip()
        tool.strengths = request.form.get("strengths", "").strip()
        tool.weaknesses = request.form.get("weaknesses", "").strip()
        tool.best_for = request.form.get("best_for", "").strip()
        tool.website = request.form.get("website", "").strip()
        tool.launched = request.form.get("launched", "").strip()
        tool.featured = bool(request.form.get("featured"))
        selected_cat_ids = [int(i) for i in request.form.getlist("categories")]
        tool.categories = Category.query.filter(
            Category.id.in_(selected_cat_ids)
        ).all()
        if tool_id is None:
            db.session.add(tool)
        db.session.commit()
        flash(f"Saved {tool.name}", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template(
        "admin/tool_form.html",
        tool=tool,
        companies=companies,
        categories=categories,
    )


@app.route("/admin/tools/<int:tool_id>/delete", methods=["POST"])
def admin_tool_delete(tool_id):
    if not admin_required():
        return redirect(url_for("admin_login"))
    tool = Tool.query.get_or_404(tool_id)
    db.session.delete(tool)
    db.session.commit()
    flash(f"Deleted {tool.name}", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/companies/new", methods=["POST"])
def admin_company_new():
    if not admin_required():
        return redirect(url_for("admin_login"))
    name = request.form.get("name", "").strip()
    if name:
        c = Company(
            name=name,
            slug=slugify(name),
            description=request.form.get("description", "").strip(),
            website=request.form.get("website", "").strip(),
            founded=request.form.get("founded", "").strip(),
            hq=request.form.get("hq", "").strip(),
        )
        db.session.add(c)
        db.session.commit()
        flash(f"Added company {name}", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/categories/new", methods=["POST"])
def admin_category_new():
    if not admin_required():
        return redirect(url_for("admin_login"))
    name = request.form.get("name", "").strip()
    if name:
        c = Category(
            name=name,
            slug=slugify(name),
            description=request.form.get("description", "").strip(),
            icon=request.form.get("icon", "").strip(),
            sort_order=int(request.form.get("sort_order") or 100),
        )
        db.session.add(c)
        db.session.commit()
        flash(f"Added category {name}", "success")
    return redirect(url_for("admin_dashboard"))


@app.cli.command("init-db")
def init_db():
    db.create_all()
    print("DB initialized")


@app.cli.command("seed")
def seed_cmd():
    from seed import run_seed

    run_seed(app, db)
    print("Seed complete")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5050)
