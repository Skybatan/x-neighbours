/**
 * X Neighbours report page.
 * report_page.py replaces the placeholder below with the report object.
 * The only import is "grok/canvas". Data is inline. This file does not fetch.
 */
import { Divider, Image, Page, Section, Text, TextLink } from "grok/canvas";

type Part = { text: string; href: string | null };
type Line = { parts: Part[] };
type Item = { lines: Line[] };
type NoteBlock = { kind: "note"; text: string };
type SectionBlock = {
  kind: "section";
  heading: string;
  preface: string | null;
  items: Item[];
  footers: string[];
};
type ThanksBlock = {
  kind: "thanks";
  text: string;
  linkLabel: string | null;
  href: string | null;
  note: string | null;
  extra: string | null;
  picture: string | null;
};
type Block = NoteBlock | SectionBlock | ThanksBlock;
type Report = {
  title: string;
  summary: string;
  legend: string | null;
  intro: string | null;
  blocks: Block[];
};

const report: Report = /*__REPORT_JSON__*/ null as unknown as Report;

function LineText({ line }: { line: Line }) {
  return (
    <Text>
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

function SectionBody({ block }: { block: SectionBlock }) {
  const lines: { key: string; line: Line }[] = [];
  block.items.forEach((item, itemIndex) => {
    item.lines.forEach((line, lineIndex) => {
      lines.push({ key: `${itemIndex}-${lineIndex}`, line });
    });
  });
  return (
    <Section heading={block.heading}>
      {block.preface ? <Text>{block.preface}</Text> : null}
      {lines.map((entry) => (
        <LineText key={entry.key} line={entry.line} />
      ))}
      {block.footers.map((footer, index) => (
        <Text key={`footer-${index}`}>{footer}</Text>
      ))}
    </Section>
  );
}

function Thanks({ block }: { block: ThanksBlock }) {
  return (
    <Section>
      <Divider />
      <Text>{block.text}</Text>
      {block.href && block.linkLabel ? (
        <Text>
          <TextLink href={block.href}>{block.linkLabel}</TextLink>
        </Text>
      ) : null}
      {block.note ? <Text>{block.note}</Text> : null}
      {block.extra ? <Text>{block.extra}</Text> : null}
      {block.picture ? (
        <Image src={block.picture} alt="House-framed neighbours picture." />
      ) : null}
    </Section>
  );
}

export default function XNeighboursReport() {
  return (
    <Page title={report.title} summary={report.summary}>
      {report.legend ? <Text>{report.legend}</Text> : null}
      {report.intro ? <Text>{report.intro}</Text> : null}
      {report.blocks.map((block, index) => {
        if (block.kind === "note") {
          return <Text key={index}>{block.text}</Text>;
        }
        if (block.kind === "thanks") {
          return <Thanks key={index} block={block} />;
        }
        if (!block.items.length && !block.preface && block.footers.length === 0) {
          return null;
        }
        return <SectionBody key={index} block={block} />;
      })}
    </Page>
  );
}
