/**
 * Good Neighbours Newsletter. It is not the Period Report.
 * good_neighbours_page.py replaces the placeholder below.
 * The only import is "grok/canvas". Data is inline. This file does not fetch.
 *
 * Kit blocks sit directly inside Page or Section.
 * Helpers are functions called as {fn(data)}, not components.
 */
import { Page, Section, Text, TextLink } from "grok/canvas";

type Part = { text: string; href: string | null };
type Line = { parts: Part[] };
type Item = { lines: Line[] };
type SectionBlock = {
  heading: string;
  explainer: string | null;
  preface: string | null;
  items: Item[];
  footers: string[];
};
type NeighboursPage = {
  title: string;
  summary: string;
  intro: string | null;
  sections: SectionBlock[];
};

const page: NeighboursPage = /*__PAGE_JSON__*/ null as unknown as NeighboursPage;

function lineText(line: Line, key: string) {
  return (
    <Text key={key}>
      {line.parts.map((part, index) =>
        part.href ? (
          <TextLink key={index} href={part.href}>
            {part.text}
          </TextLink>
        ) : (
          part.text
        ),
      )}
    </Text>
  );
}

function sectionNodes(block: SectionBlock) {
  const nodes = [];
  if (block.explainer) {
    nodes.push(<Text key="explainer">{block.explainer}</Text>);
  }
  if (block.preface) {
    nodes.push(<Text key="preface">{block.preface}</Text>);
  }
  block.items.forEach((item, itemIndex) => {
    item.lines.forEach((line, lineIndex) => {
      nodes.push(lineText(line, `${itemIndex}-${lineIndex}`));
    });
  });
  block.footers.forEach((footer, index) => {
    nodes.push(<Text key={`footer-${index}`}>{footer}</Text>);
  });
  return nodes;
}

export default function GoodNeighboursPage() {
  return (
    <Page title={page.title} summary={page.summary}>
      {page.intro ? <Text>{page.intro}</Text> : null}
      {page.sections.map((block, index) => (
        <Section key={index} heading={block.heading}>
          {sectionNodes(block)}
        </Section>
      ))}
    </Page>
  );
}
