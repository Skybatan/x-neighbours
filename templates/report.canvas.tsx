/**
 * Period Report page.
 * report_page.py replaces the placeholder below with the report object.
 * The only import is "grok/canvas". Data is inline. This file does not fetch.
 *
 * Kit blocks (Page, Section, Text, Divider, Image) sit directly inside
 * Page or Section. Helpers are functions called as {fn(data)}, not components.
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
  explainer: string | null;
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
  explainer: string | null;
  picture: string | null;
  pictureAlt: string | null;
  pictureRatio: number | string | null;
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

function introLines(intro: string | null) {
  // The welcome tour's first line is the greeting, including the owner's name.
  // `intro` is JSON data embedded by report_page.py. The name stays inside that
  // string; it is not interpolated into the template source.
  if (!intro) return null;
  return intro
    .split("\n")
    .filter((line) => line.length > 0)
    .map((line, index) => <Text key={`intro-${index}`}>{line}</Text>);
}

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

function thanksNodes(block: ThanksBlock) {
  const nodes = [];
  nodes.push(<Divider key="rule" />);
  if (block.explainer) {
    nodes.push(<Text key="explainer">{block.explainer}</Text>);
  }
  if (block.text) {
    nodes.push(<Text key="text">{block.text}</Text>);
  }
  if (block.href && block.linkLabel) {
    nodes.push(
      <Text key="link">
        <TextLink href={block.href}>{block.linkLabel}</TextLink>
      </Text>,
    );
  }
  if (block.note) {
    nodes.push(<Text key="note">{block.note}</Text>);
  }
  if (block.extra) {
    nodes.push(<Text key="extra">{block.extra}</Text>);
  }
  if (block.picture) {
    const alt = block.pictureAlt || "Neighbours Picture Day.";
    if (block.pictureRatio) {
      nodes.push(
        <Image key="picture" src={block.picture} alt={alt} ratio={block.pictureRatio} />,
      );
    } else {
      nodes.push(<Image key="picture" src={block.picture} alt={alt} />);
    }
  }
  return nodes;
}

export default function XNeighboursReport() {
  return (
    <Page title={report.title} summary={report.summary}>
      {introLines(report.intro)}
      {report.legend ? <Text>{report.legend}</Text> : null}
      {report.blocks.map((block, index) => {
        if (block.kind === "note") {
          return <Text key={index}>{block.text}</Text>;
        }
        if (block.kind === "thanks") {
          return (
            <Section key={index}>
              {thanksNodes(block)}
            </Section>
          );
        }
        if (!block.items.length && !block.preface && !block.explainer && block.footers.length === 0) {
          return null;
        }
        return (
          <Section key={index} heading={block.heading}>
            {sectionNodes(block)}
          </Section>
        );
      })}
    </Page>
  );
}
