import os
import sys
import click
from sutra.parser.triage import TriageScanner
from sutra.parser.docx import DocxParser

@click.group()
def cli():
    """Sutra Press: Academic Manuscript Conversion Engine CLI."""
    pass

@cli.command()
@click.argument("input_file", type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.option("--out", "-o", required=True, type=click.Path(file_okay=False, dir_okay=True), help="Directory to write output package.")
@click.option("--force", is_flag=True, help="Force conversion even if triage reports errors.")
@click.option("--layout", "-l", type=click.Choice(["single", "double"]), default="single", help="Column layout (single or double).")
def convert(input_file, out, force, layout):
    """
    Ingests DOCX manuscript, runs triage, parses content to IR,
    and produces JATS XML, LaTeX, and compiled PDF.
    """
    click.echo(f"Starting conversion for: {input_file}")
    
    # 1. Determine output subdirectory slug
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    output_dir = os.path.join(out, base_name)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "assets"), exist_ok=True)

    # 2. Run pre-flight triage
    click.echo("Running pre-flight triage...")
    scanner = TriageScanner(input_file)
    triage_report = scanner.run_triage()
    
    # Write triage report
    triage_report_path = os.path.join(output_dir, "triage-report.md")
    with open(triage_report_path, "w", encoding="utf-8") as f:
        f.write(triage_report.to_markdown())
    click.echo(f"Triage report written to: {triage_report_path}")

    # Check triage verdict
    if triage_report.verdict == "needs-manual-prep" and not force:
        click.echo("Triage failed with errors. Aborting conversion. Use --force to override.", err=True)
        sys.exit(1)
    elif triage_report.verdict == "pass-with-warnings":
        click.echo("Triage passed with warnings. Continuing...")
    else:
        click.echo("Triage passed successfully.")

    # 3. Parse DOCX AST -> IR
    click.echo("Parsing manuscript structures...")
    try:
        parser = DocxParser(input_file)
        doc = parser.parse()
        click.echo(f"Successfully parsed document IR: {len(doc.body)} body sections found.")
    except Exception as e:
        click.echo(f"Error parsing document: {str(e)}", err=True)
        sys.exit(1)

    # 4. Generate JATS XML
    click.echo("Generating JATS XML...")
    from sutra.generator.jats import JatsGenerator
    from sutra.utils.xml import validate_jats_xml

    try:
        generator = JatsGenerator()
        xml_bytes = generator.generate(doc)
        
        article_xml_path = os.path.join(output_dir, "article.xml")
        with open(article_xml_path, "wb") as f:
            f.write(xml_bytes)
            
        # Run JATS validation
        click.echo("Validating JATS XML against schema...")
        errors = validate_jats_xml(xml_bytes)
        
        # Write validation report
        validation_report_path = os.path.join(output_dir, "validation-report.md")
        with open(validation_report_path, "w", encoding="utf-8") as f:
            f.write("# JATS XML Validation Report\n\n")
            if not errors:
                f.write("**Status**: PASSED\n\nThe XML document is valid against the NISO JATS 1.3 schema.\n")
            else:
                f.write("**Status**: FAILED\n\n")
                f.write("## Validation Errors\n")
                for err in errors:
                    f.write(f"- {err}\n")
                    
        if errors and not force:
            click.echo("JATS XML validation failed against schema. Aborting. Use --force to override.", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error during JATS XML generation or validation: {str(e)}", err=True)
        sys.exit(1)

    # 5. Generate LaTeX
    click.echo("Generating LaTeX source...")
    from sutra.generator.latex import LatexGenerator
    from sutra.utils.latex import compile_latex_to_pdf

    try:
        latex_gen = LatexGenerator()
        tex_source = latex_gen.generate(doc, layout=layout)
        
        article_tex_path = os.path.join(output_dir, "article.tex")
        with open(article_tex_path, "w", encoding="utf-8") as f:
            f.write(tex_source)
            
        # 6. Compile LaTeX to PDF using Tectonic
        click.echo("Compiling LaTeX to PDF using Tectonic (this may take a few seconds)...")
        compile_errors = compile_latex_to_pdf(article_tex_path, output_dir)
        
        if compile_errors:
            click.echo("LaTeX compilation failed with the following errors:", err=True)
            for err in compile_errors:
                click.echo(f"  - {err}", err=True)
            if not force:
                click.echo("Aborting. Use --force to write output anyway.", err=True)
                sys.exit(1)
        else:
            click.echo("LaTeX compiled to PDF successfully.")

    except Exception as e:
        click.echo(f"Error during LaTeX generation or compilation: {str(e)}", err=True)
        sys.exit(1)

    click.echo(f"Conversion packaged successfully in: {output_dir}")


if __name__ == "__main__":
    cli()
