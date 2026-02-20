"""CSS legacy v0.1 — gardé pour fallback quand libsass est absent."""


def get_modules_css() -> str:
    """CSS minimal des blocs v0.1 (hero, pricing, cta, testimonials, proof)."""
    return """
.hero{text-align:center;padding:4rem 1rem}
.hero h1{font-size:2.5rem;margin-bottom:1rem}
.hero p{font-size:1.1rem;color:var(--color-text-light);margin-bottom:1.5rem}
.hero-btns{display:flex;gap:1rem;justify-content:center;flex-wrap:wrap}
.pricing{padding:3rem 0}
.pricing-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1.5rem;max-width:1100px;margin:0 auto}
.pricing-card{background:var(--color-bg);border:1px solid var(--color-border);border-radius:var(--border-radius-lg);padding:1.5rem}
.pricing-card.featured{border-color:var(--color-primary);border-width:2px}
.pricing-name{font-size:1.2rem;font-weight:700;margin-bottom:.5rem}
.pricing-price{font-size:2rem;font-weight:800;color:var(--color-primary);margin-bottom:1rem}
.pricing-features{list-style:none;margin-bottom:1rem}
.pricing-features li{padding:.4rem 0;border-bottom:1px solid var(--color-bg-gray)}
.pricing-features li::before{content:"✓ ";color:var(--color-primary);font-weight:700}
.cta{text-align:center;padding:3rem 1rem;background:linear-gradient(135deg,var(--color-primary),var(--color-secondary));color:#fff;border-radius:var(--border-radius-lg)}
.cta h2,.cta p{color:#fff}
.testimonials{padding:3rem 0}
.testimonials-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1.5rem}
.testimonial-card{background:var(--color-bg-gray);padding:1.5rem;border-radius:var(--border-radius-md)}
.proof{padding:3rem 0;background:var(--color-bg-gray)}
.proof-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1.5rem}
.proof-stat{text-align:center}
.proof-value{font-size:2.5rem;font-weight:800;color:var(--color-primary);margin-bottom:.5rem}
.proof-label{color:var(--color-text-light)}
""".strip()
