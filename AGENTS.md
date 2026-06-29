import { createFileRoute } from "@tanstack/react-router";
import { Check } from "lucide-react";
import aboutImg from "@/assets/about.jpg";
import heroImg from "@/assets/hero.jpg";
import { SiteHeader, SiteFooter, PageHero, CTASection } from "@/components/site";

export const Route = createFileRoute("/ueber-uns")({
  head: () => ({
    meta: [
      { title: "Über uns – Gjini Gartenbau" },
      { name: "description", content: "Familienunternehmen aus Niederlenz AG. Seit 1997 realisieren wir hochwertige Gartenprojekte mit Sorgfalt und Leidenschaft." },
      { property: "og:title", content: "Über uns – Gjini Gartenbau" },
      { property: "og:description", content: "Seit über 25 Jahren persönliche Beratung und handwerkliche Qualität." },
      { property: "og:url", content: "/ueber-uns" },
    ],
    links: [{ rel: "canonical", href: "/ueber-uns" }],
  }),
  component: AboutPage,
});

function AboutPage() {
  const values = [
    { t: "Persönliche Beratung", d: "Direkter Kontakt zum Inhaber – vom ersten Gespräch bis zur Übergabe." },
    { t: "Saubere Ausführung", d: "Wir arbeiten strukturiert, halten Termine und übergeben besenrein." },
    { t: "Hohe Qualität", d: "Sorgfältige Materialwahl und handwerkliche Präzision in jedem Detail." },
    { t: "Zuverlässigkeit", d: "Verbindliche Zusagen, transparente Kommunikation und faire Preise." },
  ];

  return (
    <div className="min-h-screen bg-background">
      <SiteHeader />
      <PageHero
        eyebrow="Über uns"
        title="Familienunternehmen aus Niederlenz AG."
        subtitle="Seit über 25 Jahren realisieren wir hochwertige Gartenprojekte in der Region – mit Leidenschaft, Präzision und einem feinen Gespür für das Wesentliche."
        image={heroImg}
      />

      <section className="py-24 md:py-32">
        <div className="container-page grid items-start gap-12 md:grid-cols-2 md:gap-20">
          <div className="relative">
            <img src={aboutImg} alt="Team von Gjini Gartenbau bei der Arbeit" width={1280} height={1280} loading="lazy" className="aspect-[4/5] w-full rounded-lg object-cover shadow-card" />
            <div className="absolute -bottom-6 -right-4 hidden rounded-lg bg-primary px-7 py-5 text-primary-foreground shadow-card md:block">
              <div className="font-display text-4xl font-semibold leading-none">25+</div>
              <div className="mt-1.5 text-xs uppercase tracking-[0.18em] opacity-80">Jahre Erfahrung</div>
            </div>
          </div>
          <div>
            <p className="eyebrow">Unsere Geschichte</p>
            <h2 className="mt-4 font-display text-3xl font-semibold leading-tight sm:text-4xl">
              Gartenbau mit Handschrift.
            </h2>
            <div className="mt-6 space-y-5 text-base leading-relaxed text-muted-foreground md:text-lg">
              <p>
                1997 in Niederlenz gegründet, ist Gjini Gartenbau heute ein etabliertes Familienunternehmen mit einem festen Stamm an erfahrenen Mitarbeitenden. Unsere Schwerpunkte liegen in Gartenbau, Gartengestaltung, Gartenpflege, Natursteinarbeiten, Terrassen, Wasseranlagen, Zäunen und Umgebungsarbeiten.
              </p>
              <p>
                Wir verstehen jeden Garten als eigenständiges Werk – geprägt von Ort, Architektur und den Menschen, die ihn nutzen. Aus dieser Haltung entstehen Anlagen, die nicht nur schön aussehen, sondern über Jahre Freude bereiten.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="bg-sand py-24 md:py-32">
        <div className="container-page">
          <div className="max-w-2xl">
            <p className="eyebrow">Unsere Werte</p>
            <h2 className="mt-4 font-display text-3xl font-semibold leading-tight sm:text-4xl">
              Was uns auszeichnet.
            </h2>
          </div>
          <ul className="mt-14 grid gap-6 sm:grid-cols-2">
            {values.map((v) => (
              <li key={v.t} className="rounded-lg border border-border bg-card p-7 transition hover:border-sage hover:shadow-soft">
                <div className="flex items-center gap-3">
                  <span className="grid h-9 w-9 place-items-center rounded-full bg-sage text-primary-foreground">
                    <Check className="h-4 w-4" strokeWidth={3} />
                  </span>
                  <h3 className="font-display text-lg font-semibold">{v.t}</h3>
                </div>
                <p className="mt-4 text-sm leading-relaxed text-muted-foreground">{v.d}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <CTASection />
      <SiteFooter />
    </div>
  );
}
