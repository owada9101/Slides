"""Folder creation must preserve source assets and reject accidental overwrites."""
import argparse
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
spec = importlib.util.spec_from_file_location('slides', Path(__file__).resolve().parents[1] / 'scripts/slides.py')
slides = importlib.util.module_from_spec(spec)
spec.loader.exec_module(slides)


class ScaffoldTests(unittest.TestCase):
    def test_clone_keeps_html_and_other_source_assets(self):
        original_root = slides.ROOT
        with tempfile.TemporaryDirectory() as temp:
            slides.ROOT = Path(temp)
            try:
                source = slides.ROOT / 'decks/source'
                source.mkdir(parents=True)
                (source / 'slides.qmd').write_text('## Original')
                (source / 'memo.md').write_text('Notes')
                figure = source / 'assets/html/figure'
                figure.mkdir(parents=True)
                (figure / 'index.html').write_text('<p>Figure</p>')
                (source / 'assets/paper.pdf').write_bytes(b'PDF source asset')
                args = argparse.Namespace(name='copy', source='source', title=None)
                slides.create_deck(args)
                target = slides.ROOT / 'decks/copy'
                self.assertEqual((target / 'assets/html/figure/index.html').read_text(), '<p>Figure</p>')
                self.assertEqual((target / 'assets/paper.pdf').read_bytes(), b'PDF source asset')
                with self.assertRaises(ValueError):
                    slides.create_deck(args)
                self.assertEqual((target / 'slides.qmd').read_text(), '## Original')
                slides.create_animation(argparse.Namespace(deck='copy', name='animation'))
                html = target / 'assets/html/animation/index.html'
                self.assertEqual((html.parent / '../../../../../shared/frame.js').resolve(), (slides.ROOT / 'shared/frame.js').resolve())
                self.assertTrue(html.is_file())
                with self.assertRaises(ValueError):
                    slides.create_animation(argparse.Namespace(deck='missing', name='figure'))
            finally:
                slides.ROOT = original_root

    def test_names_cannot_escape_deck_folder(self):
        for name in ('../escape', '/tmp/escape', '.', 'a/b', 'a b'):
            with self.subTest(name=name), self.assertRaises(argparse.ArgumentTypeError):
                slides.name(name)
        self.assertEqual(slides.name('2026-11-01_院ゼミ'), '2026-11-01_院ゼミ')

    def test_reveal_staging_preserves_body_and_resolves_shared_files(self):
        root = Path(__file__).resolve().parents[1]
        for name in ('2026-10-21', 'NICT2026-10-06'):
            with self.subTest(deck=name):
                self.assertTrue(slides.is_revealjs(name))
                source, metadata = slides.revealjs.staged_source(root, name)
                original = (root / 'decks' / name / 'slides.qmd').read_text()
                self.assertEqual(source.read_text().split('---', 2)[2], original.split('---', 2)[2])
                self.assertTrue(Path(metadata['format']['revealjs']['theme'][1]).is_file())
                self.assertTrue(Path(metadata['format']['pptx']['reference-doc']).is_file())
                for value in metadata['format']['pptx']['filters']:
                    self.assertTrue(Path(value).is_file())
        # Sample decks can change format; use a dedicated HTML fixture.
        original_root = slides.ROOT
        with tempfile.TemporaryDirectory() as temp:
            slides.ROOT = Path(temp)
            try:
                folder = slides.ROOT / 'decks/html'
                folder.mkdir(parents=True)
                (folder / 'slides.qmd').write_text('---\nformat: html\n---\n## HTML')
                self.assertFalse(slides.is_revealjs('html'))
            finally:
                slides.ROOT = original_root


if __name__ == '__main__':
    unittest.main()
