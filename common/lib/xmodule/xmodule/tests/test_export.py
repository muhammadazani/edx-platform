"""
Tests of XML export
"""

from datetime import datetime, timedelta, tzinfo
from tempfile import mkdtemp
import unittest
import shutil
from textwrap import dedent
import mock

import pytz
from fs.osfs import OSFS
from path import path
import uuid
import tarfile
import os

from xmodule.modulestore import Location
from xmodule.modulestore.xml import XMLModuleStore
from xmodule.modulestore.xml_exporter import (
    EdxJSONEncoder, convert_between_versions, get_version
)
from xmodule.tests import DATA_DIR
from xmodule.tests.helpers import directories_equal


def strip_filenames(descriptor):
    """
    Recursively strips 'filename' from all children's definitions.
    """
    print("strip filename from {desc}".format(desc=descriptor.location.url()))
    if descriptor._field_data.has(descriptor, 'filename'):
        descriptor._field_data.delete(descriptor, 'filename')

    if hasattr(descriptor, 'xml_attributes'):
        if 'filename' in descriptor.xml_attributes:
            del descriptor.xml_attributes['filename']

    for d in descriptor.get_children():
        strip_filenames(d)

    descriptor.save()


class RoundTripTestCase(unittest.TestCase):
    """
    Check that our test courses roundtrip properly.
    Same course imported , than exported, then imported again.
    And we compare original import with second import (after export).
    Thus we make sure that export and import work properly.
    """

    @mock.patch('xmodule.course_module.requests.get')
    def check_export_roundtrip(self, data_dir, course_dir, mock_get):

        # Patch network calls to retrieve the textbook TOC
        mock_get.return_value.text = dedent("""
            <?xml version="1.0"?><table_of_contents>
            <entry page="5" page_label="ii" name="Table of Contents"/>
            </table_of_contents>
        """).strip()

        root_dir = path(self.temp_dir)
        print("Copying test course to temp dir {0}".format(root_dir))

        data_dir = path(data_dir)
        shutil.copytree(data_dir / course_dir, root_dir / course_dir)

        print("Starting import")
        initial_import = XMLModuleStore(root_dir, course_dirs=[course_dir])

        courses = initial_import.get_courses()
        self.assertEquals(len(courses), 1)
        initial_course = courses[0]

        # export to the same directory--that way things like the custom_tags/ folder
        # will still be there.
        print("Starting export")
        fs = OSFS(root_dir)
        export_fs = fs.makeopendir(course_dir)

        xml = initial_course.export_to_xml(export_fs)
        with export_fs.open('course.xml', 'w') as course_xml:
            course_xml.write(xml)

        print("Starting second import")
        second_import = XMLModuleStore(root_dir, course_dirs=[course_dir])

        courses2 = second_import.get_courses()
        self.assertEquals(len(courses2), 1)
        exported_course = courses2[0]

        print("Checking course equality")

        # HACK: filenames change when changing file formats
        # during imports from old-style courses.  Ignore them.
        strip_filenames(initial_course)
        strip_filenames(exported_course)

        self.assertEquals(initial_course, exported_course)
        self.assertEquals(initial_course.id, exported_course.id)
        course_id = initial_course.id

        print("Checking key equality")
        self.assertEquals(sorted(initial_import.modules[course_id].keys()),
                          sorted(second_import.modules[course_id].keys()))

        print("Checking module equality")
        for location in initial_import.modules[course_id].keys():
            print("Checking", location)
            self.assertEquals(initial_import.modules[course_id][location],
                              second_import.modules[course_id][location])

    def setUp(self):
        self.maxDiff = None
        self.temp_dir = mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir)

    def test_toy_roundtrip(self):
        self.check_export_roundtrip(DATA_DIR, "toy")

    def test_simple_roundtrip(self):
        self.check_export_roundtrip(DATA_DIR, "simple")

    def test_conditional_and_poll_roundtrip(self):
        self.check_export_roundtrip(DATA_DIR, "conditional_and_poll")

    def test_conditional_roundtrip(self):
        self.check_export_roundtrip(DATA_DIR, "conditional")

    def test_selfassessment_roundtrip(self):
        #Test selfassessment xmodule to see if it exports correctly
        self.check_export_roundtrip(DATA_DIR, "self_assessment")

    def test_graphicslidertool_roundtrip(self):
        #Test graphicslidertool xmodule to see if it exports correctly
        self.check_export_roundtrip(DATA_DIR, "graphic_slider_tool")

    def test_exam_registration_roundtrip(self):
        # Test exam_registration xmodule to see if it exports correctly
        self.check_export_roundtrip(DATA_DIR, "test_exam_registration")

    def test_word_cloud_roundtrip(self):
        self.check_export_roundtrip(DATA_DIR, "word_cloud")


class TestEdxJsonEncoder(unittest.TestCase):
    """
    Tests for xml_exporter.EdxJSONEncoder
    """
    def setUp(self):
        self.encoder = EdxJSONEncoder()

        class OffsetTZ(tzinfo):
            """A timezone with non-None utcoffset"""
            def utcoffset(self, _dt):
                return timedelta(hours=4)

        self.offset_tz = OffsetTZ()

        class NullTZ(tzinfo):
            """A timezone with None as its utcoffset"""
            def utcoffset(self, _dt):
                return None
        self.null_utc_tz = NullTZ()

    def test_encode_location(self):
        loc = Location('i4x', 'org', 'course', 'category', 'name')
        self.assertEqual(loc.url(), self.encoder.default(loc))

        loc = Location('i4x', 'org', 'course', 'category', 'name', 'version')
        self.assertEqual(loc.url(), self.encoder.default(loc))

    def test_encode_naive_datetime(self):
        self.assertEqual(
            "2013-05-03T10:20:30.000100",
            self.encoder.default(datetime(2013, 5, 3, 10, 20, 30, 100))
        )
        self.assertEqual(
            "2013-05-03T10:20:30",
            self.encoder.default(datetime(2013, 5, 3, 10, 20, 30))
        )

    def test_encode_utc_datetime(self):
        self.assertEqual(
            "2013-05-03T10:20:30+00:00",
            self.encoder.default(datetime(2013, 5, 3, 10, 20, 30, 0, pytz.UTC))
        )

        self.assertEqual(
            "2013-05-03T10:20:30+04:00",
            self.encoder.default(datetime(2013, 5, 3, 10, 20, 30, 0, self.offset_tz))
        )

        self.assertEqual(
            "2013-05-03T10:20:30Z",
            self.encoder.default(datetime(2013, 5, 3, 10, 20, 30, 0, self.null_utc_tz))
        )

    def test_fallthrough(self):
        with self.assertRaises(TypeError):
            self.encoder.default(None)

        with self.assertRaises(TypeError):
            self.encoder.default({})


class ConvertExportFormat(unittest.TestCase):
    """
    Tests converting between export formats.
    """
    def setUp(self):
        """ Common setup. """

        # Directory for expanding all the test archives
        self.temp_dir = mkdtemp()

        # Directory where new archive will be created
        self.result_dir = path(self.temp_dir) / uuid.uuid4().hex
        os.mkdir(self.result_dir)

        # Expand all the test archives and store their paths.
        self.data_dir = path(__file__).realpath().parent / 'data'
        self.version0_nodrafts = self._expand_archive('Version0_nodrafts.tar.gz')
        self.version1_nodrafts = self._expand_archive('Version1_nodrafts.tar.gz')
        self.version0_drafts = self._expand_archive('Version0_drafts.tar.gz')
        self.version1_drafts = self._expand_archive('Version1_drafts.tar.gz')
        self.version1_drafts_extra_branch = self._expand_archive('Version1_drafts_extra_branch.tar.gz')
        self.no_version = self._expand_archive('NoVersionNumber.tar.gz')

    def tearDown(self):
        """ Common cleanup. """
        shutil.rmtree(self.temp_dir)

    def _expand_archive(self, name):
        """ Expand archive into a directory and return the directory. """
        target = path(self.temp_dir) / uuid.uuid4().hex
        os.mkdir(target)
        with tarfile.open(self.data_dir / name) as tar_file:
            tar_file.extractall(path=target)

        return target

    def test_no_version(self):
        """ Test error condition of no version number specified. """
        errstring = "unknown version"
        with self.assertRaisesRegexp(ValueError, errstring):
            convert_between_versions(self.no_version, self.result_dir)

    def test_no_published(self):
        """ Test error condition of a version 1 archive with no published branch. """
        errstring = "version 1 archive must contain a published branch"
        no_published = self._expand_archive('Version1_nopublished.tar.gz')
        with self.assertRaisesRegexp(ValueError, errstring):
            convert_between_versions(no_published, self.result_dir)

    def test_empty_course(self):
        """ Test error condition of a version 1 archive with no published branch. """
        errstring = "source archive does not have single course directory at top level"
        empty_course = self._expand_archive('EmptyCourse.tar.gz')
        with self.assertRaisesRegexp(ValueError, errstring):
            convert_between_versions(empty_course, self.result_dir)

    def test_convert_to_1_nodrafts(self):
        """
        Test for converting from version 0 of export format to version 1 in a course with no drafts.
        """
        self._verify_conversion(self.version0_nodrafts, self.version1_nodrafts)

    def test_convert_to_1_drafts(self):
        """
        Test for converting from version 0 of export format to version 1 in a course with drafts.
        """
        self._verify_conversion(self.version0_drafts, self.version1_drafts)

    def test_convert_to_0_nodrafts(self):
        """
        Test for converting from version 1 of export format to version 0 in a course with no drafts.
        """
        self._verify_conversion(self.version1_nodrafts, self.version0_nodrafts)

    def test_convert_to_0_drafts(self):
        """
        Test for converting from version 1 of export format to version 0 in a course with drafts.
        """
        self._verify_conversion(self.version1_drafts, self.version0_drafts)

    def test_convert_to_0_extra_branch(self):
        """
        Test for converting from version 1 of export format to version 0 in a course
        with drafts and an extra branch.
        """
        self._verify_conversion(self.version1_drafts_extra_branch, self.version0_drafts)

    def test_equality_function(self):
        """
        Check equality function returns False for unequal directories.
        """
        self.assertFalse(directories_equal(self.version1_nodrafts, self.version0_nodrafts))
        self.assertFalse(directories_equal(self.version1_drafts_extra_branch, self.version1_drafts))

    def test_version_0(self):
        """
        Check that get_version correctly identifies a version 0 archive (old format).
        """
        self.assertEqual(0, self._version_test(self.version0_nodrafts))

    def test_version_1(self):
        """
        Check that get_version correctly identifies a version 1 archive (new format).
        """
        self.assertEqual(1, self._version_test(self.version1_nodrafts))

    def test_version_missing(self):
        """
        Check that get_version returns None if no version number is specified,
        and the archive is not version 0.
        """
        self.assertIsNone(self._version_test(self.no_version))

    def _version_test(self, archive_dir):
        """
        Helper function for version tests.
        """
        root = os.listdir(archive_dir)
        course_directory = archive_dir / root[0]
        return get_version(course_directory)

    def _verify_conversion(self, source_archive, comparison_archive):
        """
        Helper function for conversion tests.
        """
        convert_between_versions(source_archive, self.result_dir)
        self.assertTrue(directories_equal(self.result_dir, comparison_archive))
