import {
  ArrowRight,
  BadgeCheck,
  HeartHandshake,
  ShieldCheck,
  ShoppingBag,
  Store,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Brand } from "../components/Brand";

interface LandingPageProps {
  signedIn: boolean;
}

const values = [
  {
    title: "Trust",
    description: "Clear communication and dependable service at every step.",
    icon: ShieldCheck,
  },
  {
    title: "Quality goods",
    description: "Useful, quality products chosen with care.",
    icon: BadgeCheck,
  },
  {
    title: "Customer satisfaction",
    description: "A welcoming experience that puts people first.",
    icon: HeartHandshake,
  },
  {
    title: "Integrity",
    description: "Honest dealings and doing what we say we will do.",
    icon: Store,
  },
];

export function LandingPage({ signedIn }: LandingPageProps) {
  const workspaceLabel = signedIn ? "Open your workspace" : "Staff sign in";

  return (
    <main className="landing-page">
      <header className="landing-header">
        <Link aria-label="MJD Square home" className="landing-brand" to="/">
          <Brand />
        </Link>
        <nav aria-label="Main navigation" className="landing-nav">
          <a href="#how-it-works">How it works</a>
          <a href="#our-values">Our values</a>
        </nav>
        <Link className="landing-signin" to="/sign-in">
          {workspaceLabel}
          <ArrowRight aria-hidden="true" size={16} />
        </Link>
      </header>

      <section aria-labelledby="landing-title" className="landing-hero">
        <div className="landing-hero-copy">
          <span className="landing-kicker">
            <span className="landing-kicker-dot" />
            GOOD GOODS. FAIR DEALS. BUILT ON TRUST.
          </span>
          <h1 id="landing-title">
            A better way to buy.
            <br />
            A better way to sell.
          </h1>
          <p>
            MJD Square brings customers and quality goods together through
            straightforward buying, selling, and service you can count on.
          </p>
          <div className="landing-hero-actions">
            <a className="landing-primary-action" href="#how-it-works">
              Discover MJD Square
              <ArrowRight aria-hidden="true" size={17} />
            </a>
            <Link className="landing-secondary-action" to="/sign-in">
              {workspaceLabel}
            </Link>
          </div>
          <div className="landing-trust-note">
            <ShieldCheck aria-hidden="true" size={16} />
            <span>Trade with confidence. Every day.</span>
          </div>
        </div>

        <div aria-label="MJD Square buying and selling" className="landing-art">
          <div aria-hidden="true" className="landing-art-orbit landing-art-orbit-one" />
          <div aria-hidden="true" className="landing-art-orbit landing-art-orbit-two" />
          <div className="landing-art-card">
            <div className="landing-art-topline">
              <Brand compact />
              <span className="landing-art-label">BUY · SELL · TRUST</span>
            </div>
            <div className="landing-art-message">
              <span className="landing-art-icon"><ShoppingBag aria-hidden="true" size={20} /></span>
              <div>
                <strong>Good business, made personal.</strong>
                <span>Quality goods. People-first service.</span>
              </div>
            </div>
            <div className="landing-shelf">
              <img
                alt="Shelves stocked with assorted soft drinks, hot drinks, wine, and table water"
                className="landing-shelf-image"
                height="320"
                src="/drink-shelf.svg"
                width="960"
              />
            </div>
            <div className="landing-art-bottom">
              <span><i /> Thoughtful service</span>
              <span>Since day one</span>
            </div>
          </div>
          <div aria-hidden="true" className="landing-float-card landing-float-card-top">
            <BadgeCheck size={17} />
            <span>Quality first</span>
          </div>
          <div aria-hidden="true" className="landing-float-card landing-float-card-bottom">
            <HeartHandshake size={18} />
            <span>People matter</span>
          </div>
        </div>
      </section>

      <section aria-labelledby="how-title" className="landing-how" id="how-it-works">
        <div className="landing-section-heading">
          <span className="landing-section-label">GOOD BUSINESS, BOTH WAYS</span>
          <h2 id="how-title">Buying and selling, with care.</h2>
          <p>Simple, thoughtful trade built around what matters: good products and good people.</p>
        </div>
        <div className="landing-trade-grid">
          <article className="landing-trade-card">
            <span className="landing-trade-icon"><ShoppingBag aria-hidden="true" size={20} /></span>
            <span className="landing-trade-label">FOR BUYERS</span>
            <h3>Find what you need.</h3>
            <p>Shop quality goods and enjoy service that makes every visit feel welcome.</p>
          </article>
          <article className="landing-trade-card landing-trade-card-dark">
            <span className="landing-trade-icon"><Store aria-hidden="true" size={20} /></span>
            <span className="landing-trade-label">FOR SELLERS</span>
            <h3>Make every deal count.</h3>
            <p>Build lasting customer relationships through honest, dependable trade.</p>
          </article>
        </div>
      </section>

      <section aria-labelledby="values-title" className="landing-values" id="our-values">
        <div className="landing-section-heading">
          <span className="landing-section-label">THE MJD SQUARE PROMISE</span>
          <h2 id="values-title">What MJD Square stands for.</h2>
          <p>Our values are more than words. They shape how we serve and do business.</p>
        </div>
        <div className="landing-values-grid">
          {values.map(({ title, description, icon: Icon }, index) => (
            <article className="landing-value-card" key={title}>
              <span className="landing-value-number">0{index + 1}</span>
              <span className="landing-value-icon"><Icon aria-hidden="true" size={20} /></span>
              <h3>{title}</h3>
              <p>{description}</p>
            </article>
          ))}
        </div>
      </section>

      <footer className="landing-footer">
        <Link aria-label="MJD Square home" className="landing-brand" to="/">
          <Brand />
        </Link>
        <p>Good goods. Fair deals. Built on trust.</p>
        <Link className="landing-footer-link" to="/sign-in">{workspaceLabel}</Link>
      </footer>
    </main>
  );
}
