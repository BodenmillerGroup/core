"""test_Pipeline.py - test the CellProfiler.Pipeline module"""


import cProfile
import os
import pstats
import sys
import tempfile
import traceback
import unittest

import numpy
import numpy.lib.index_tricks
import six
import six.moves
import io

import nucleus.image
import nucleus.measurement
import nucleus.module
import nucleus.modules
import nucleus.modules.injectimage
import nucleus.modules.loadimages
import nucleus.pipeline
import nucleus.preferences
import nucleus.setting
import nucleus.workspace
import tests.modules

IMAGE_NAME = "myimage"
ALT_IMAGE_NAME = "altimage"
OBJECT_NAME = "myobject"
CATEGORY = "category"
FEATURE_NAME = "category_myfeature"


def module_directory():
    d = nucleus.pipeline.__file__
    d = os.path.split(d)[0]  # ./CellProfiler/pyCellProfiler/cellProfiler
    d = os.path.split(d)[0]  # ./CellProfiler/pyCellProfiler
    d = os.path.split(d)[0]  # ./CellProfiler
    if not d:
        d = ".."
    return os.path.join(d, "Modules")


def image_with_one_cell(size=(100, 100)):
    img = numpy.zeros(size)
    mgrid = numpy.lib.index_tricks.nd_grid()
    g = mgrid[0 : size[0], 0 : size[1]] - 50
    dist = (
        g[0, :, :] * g[0, :, :] + g[1, :, :] * g[1, :, :]
    )  # squared Euclidean distance.
    img[dist < 25] = (
        25.0 - dist.astype(float)[dist < 25]
    ) / 25  # A circle centered at (50, 50)
    return img


def get_empty_pipeline():
    pipeline = nucleus.pipeline.Pipeline()
    while len(pipeline.modules()) > 0:
        pipeline.remove_module(pipeline.modules()[-1].module_num)
    return pipeline


def exploding_pipeline(test):
    """Return a pipeline that fails if the run exception callback is called during a run
    """
    x = get_empty_pipeline()

    def fn(pipeline, event):
        if isinstance(event, nucleus.pipeline.RunExceptionEvent):
            import traceback

            test.assertFalse(
                isinstance(event, nucleus.pipeline.RunExceptionEvent),
                "\n".join([event.error.message] + traceback.format_tb(event.tb)),
            )

    x.add_listener(fn)
    return x


class TestPipeline(unittest.TestCase):
    def setUp(self):
        # Change the default output directory to a temporary file
        nucleus.preferences.set_headless()
        self.new_output_directory = os.path.normcase(tempfile.mkdtemp())
        nucleus.preferences.set_default_output_directory(self.new_output_directory)

    def tearDown(self):
        subdir = self.new_output_directory
        for filename in os.listdir(subdir):
            try:
                os.remove(os.path.join(subdir, filename))
            except:
                sys.stderr.write("Failed to remove %s" % filename)
                traceback.print_exc()
        try:
            os.rmdir(subdir)
        except:
            sys.stderr.write("Failed to remove temporary %s directory" % subdir)
            traceback.print_exc()

    def test_init(self):
        x = nucleus.pipeline.Pipeline()

    def test_is_txt_fd_sorry_for_your_proofpoint(self):
        # Regression test of issue #1318
        sensible = r"""CellProfiler Pipeline: http://www.nucleus.org
    Version:3
    DateRevision:20140723174500
    GitHash:6c2d896
    ModuleCount:17
    HasImagePlaneDetails:False"""
        proofpoint = r"""CellProfiler Pipeline: https://urldefense.proofpoint.com/v2/url?u=http-3A__www.nucleus.org&d=AwIGAg&c=4R1YgkJNMyVWjMjneTwN5tJRn8m8VqTSNCjYLg1wNX4&r=ZlgBKM1XjsDOEFy5b6o_Y9E076K1Jlt5FonpX_9mB-M&m=mjjreN4DEr49dWksH8OkXbV51OsYqIX18TSsFFmPurA&s=tQ-7XP8ph9RHRlzicZb6N-OxPxQNMXYLqkucuJS9Hys&e=
Version:3
DateRevision:20140723174500
GitHash:6c2d896
ModuleCount:17
HasImagePlaneDetails:False"""
        not_txt = r"""not CellProfiler Pipeline: http://www.nucleus.org"""
        for text, expected in ((sensible, True), (proofpoint, True), (not_txt, False)):
            fd = six.moves.StringIO(text)
            assert nucleus.pipeline.Pipeline.is_pipeline_txt_fd(fd) == expected

    def test_copy_nothing(self):
        # Regression test of issue #565
        #
        # Can't copy an empty pipeline
        #
        pipeline = nucleus.pipeline.Pipeline()
        p2 = pipeline.copy()

    def test_run_pipeline(self):
        x = exploding_pipeline(self)
        module = nucleus.modules.injectimage.InjectImage(
            "OneCell", image_with_one_cell()
        )
        module.set_module_num(1)
        x.add_module(module)
        x.run()

    def test_get_measurement_columns(self):
        """Test the get_measurement_columns method"""
        x = get_empty_pipeline()
        module = TestModuleWithMeasurement()
        module.set_module_num(1)
        module.my_variable.value = "foo"
        x.add_module(module)
        columns = x.get_measurement_columns()
        assert len(columns) == 9
        assert any(
            [
                column[0] == "Image"
                and column[1] == "Group_Number"
                and column[2] == nucleus.measurement.COLTYPE_INTEGER
                for column in columns
            ]
        )
        assert any(
            [
                column[0] == "Image"
                and column[1] == "Group_Index"
                and column[2] == nucleus.measurement.COLTYPE_INTEGER
                for column in columns
            ]
        )
        assert any(
            [
                column[0] == "Image"
                and column[1] == "ModuleError_01TestModuleWithMeasurement"
                for column in columns
            ]
        )
        assert any(
            [
                column[0] == "Image"
                and column[1] == "ExecutionTime_01TestModuleWithMeasurement"
                for column in columns
            ]
        )
        assert any(
            [
                column[0] == nucleus.measurement.EXPERIMENT
                and column[1] == nucleus.pipeline.M_PIPELINE
                for column in columns
            ]
        )
        assert any(
            [
                column[0] == nucleus.measurement.EXPERIMENT
                and column[1] == nucleus.pipeline.M_VERSION
                for column in columns
            ]
        )
        assert any(
            [
                column[0] == nucleus.measurement.EXPERIMENT
                and column[1] == nucleus.pipeline.M_TIMESTAMP
                for column in columns
            ]
        )
        assert any(
            [
                len(columns) > 3
                and column[0] == nucleus.measurement.EXPERIMENT
                and column[1] == nucleus.pipeline.M_MODIFICATION_TIMESTAMP
                and column[3][nucleus.measurement.MCA_AVAILABLE_POST_RUN]
                for column in columns
            ]
        )

        assert any([column[1] == "foo" for column in columns])
        module.my_variable.value = "bar"
        columns = x.get_measurement_columns()
        assert len(columns) == 9
        assert any([column[1] == "bar" for column in columns])
        module = TestModuleWithMeasurement()
        module.set_module_num(2)
        module.my_variable.value = "foo"
        x.add_module(module)
        columns = x.get_measurement_columns()
        assert len(columns) == 12
        assert any([column[1] == "foo" for column in columns])
        assert any([column[1] == "bar" for column in columns])
        columns = x.get_measurement_columns(module)
        assert len(columns) == 9
        assert any([column[1] == "bar" for column in columns])

    def test_all_groups(self):
        """Test running a pipeline on all groups"""
        pipeline = exploding_pipeline(self)
        expects = ["PrepareRun", 0]
        keys = ("foo", "bar")
        groupings = (
            ({"foo": "foo-A", "bar": "bar-A"}, (1, 2)),
            ({"foo": "foo-B", "bar": "bar-B"}, (3, 4)),
        )

        def prepare_run(workspace):
            image_set_list = workspace.image_set_list
            assert expects[0] == "PrepareRun"
            for group_number_idx, (grouping, image_numbers) in enumerate(groupings):
                for group_idx, image_number in enumerate(image_numbers):
                    workspace.measurements[
                        nucleus.measurement.IMAGE,
                        nucleus.measurement.GROUP_NUMBER,
                        image_number,
                    ] = (group_number_idx + 1)
                    workspace.measurements[
                        nucleus.measurement.IMAGE,
                        nucleus.measurement.GROUP_INDEX,
                        image_number,
                    ] = (group_idx + 1)
            expects[0], expects[1] = ("PrepareGroup", 0)
            return True

        def prepare_group(workspace, grouping, image_numbers):
            expects_state, expects_grouping = expects
            assert expects_state == "PrepareGroup"
            if expects_grouping == 0:
                expects[0], expects[1] = ("Run", 1)
                assert image_numbers == (1, 2)
            else:
                expects[0], expects[1] = ("Run", 3)
                assert image_numbers == (3, 4)
            return True

        def run(workspace):
            expects_state, expects_image_number = expects
            image_number = workspace.measurements.image_set_number
            assert expects_state == "Run"
            assert expects_image_number == image_number
            if image_number == 1:
                expects[0], expects[1] = ("Run", 2)
            elif image_number == 3:
                expects[0], expects[1] = ("Run", 4)
            elif image_number == 2:
                expects[0], expects[1] = ("PostGroup", 0)
            else:
                expects[0], expects[1] = ("PostGroup", 1)
            workspace.measurements.add_image_measurement("mymeasurement", image_number)

        def post_group(workspace, grouping):
            expects_state, expects_grouping = expects
            assert expects_state == "PostGroup"
            for key in keys:
                assert key in grouping
                value = groupings[expects_grouping][0][key]
                assert grouping[key] == value
            if expects_grouping == 0:
                assert workspace.measurements.image_set_number == 2
                expects[0], expects[1] = ("PrepareGroup", 1)
            else:
                assert workspace.measurements.image_set_number == 4
                expects[0], expects[1] = ("PostRun", 0)

        def post_run(workspace):
            assert expects[0] == "PostRun"
            expects[0], expects[1] = ("Done", 0)

        def get_measurement_columns(pipeline):
            return [
                (
                    nucleus.measurement.IMAGE,
                    "mymeasurement",
                    nucleus.measurement.COLTYPE_INTEGER,
                )
            ]

        module = GroupModule()
        module.setup(
            (keys, groupings),
            prepare_run,
            prepare_group,
            run,
            post_group,
            post_run,
            get_measurement_columns,
        )
        module.set_module_num(1)
        pipeline.add_module(module)
        measurements = pipeline.run()
        assert expects[0] == "Done"
        image_numbers = measurements.get_all_measurements("Image", "mymeasurement")
        assert len(image_numbers) == 4
        assert numpy.all(image_numbers == numpy.array([1, 2, 3, 4]))
        group_numbers = measurements.get_all_measurements("Image", "Group_Number")
        assert numpy.all(group_numbers == numpy.array([1, 1, 2, 2]))
        group_indexes = measurements.get_all_measurements("Image", "Group_Index")
        assert numpy.all(group_indexes == numpy.array([1, 2, 1, 2]))

    def test_one_group(self):
        """Test running a pipeline on one group"""
        pipeline = exploding_pipeline(self)
        expects = ["PrepareRun", 0]
        keys = ("foo", "bar")
        groupings = (
            ({"foo": "foo-A", "bar": "bar-A"}, (1, 2)),
            ({"foo": "foo-B", "bar": "bar-B"}, (3, 4)),
            ({"foo": "foo-C", "bar": "bar-C"}, (5, 6)),
        )

        def prepare_run(workspace):
            assert expects[0] == "PrepareRun"
            for group_number_idx, (grouping, image_numbers) in enumerate(groupings):
                for group_idx, image_number in enumerate(image_numbers):
                    workspace.measurements[
                        nucleus.measurement.IMAGE,
                        nucleus.measurement.GROUP_NUMBER,
                        image_number,
                    ] = (group_number_idx + 1)
                    workspace.measurements[
                        nucleus.measurement.IMAGE,
                        nucleus.measurement.GROUP_INDEX,
                        image_number,
                    ] = (group_idx + 1)
            expects[0], expects[1] = ("PrepareGroup", 1)
            return True

        def prepare_group(workspace, grouping, *args):
            expects_state, expects_grouping = expects
            assert expects_state == "PrepareGroup"
            for key in keys:
                assert key in grouping
                value = groupings[expects_grouping][0][key]
                assert grouping[key] == value
            assert expects_grouping == 1
            expects[0], expects[1] = ("Run", 3)
            return True

        def run(workspace):
            expects_state, expects_image_number = expects
            image_number = workspace.measurements.image_set_number
            assert expects_state == "Run"
            assert expects_image_number == image_number
            if image_number == 3:
                expects[0], expects[1] = ("Run", 4)
            elif image_number == 4:
                expects[0], expects[1] = ("PostGroup", 1)

            workspace.measurements.add_image_measurement("mymeasurement", image_number)

        def post_group(workspace, grouping):
            expects_state, expects_grouping = expects
            assert expects_state == "PostGroup"
            for key in keys:
                assert key in grouping
                value = groupings[expects_grouping][0][key]
                assert grouping[key] == value
            expects[0], expects[1] = ("PostRun", 0)

        def post_run(workspace):
            assert expects[0] == "PostRun"
            expects[0], expects[1] = ("Done", 0)

        def get_measurement_columns(pipeline):
            return [
                (
                    nucleus.measurement.IMAGE,
                    "mymeasurement",
                    nucleus.measurement.COLTYPE_INTEGER,
                )
            ]

        module = GroupModule()
        module.setup(
            (keys, groupings),
            prepare_run,
            prepare_group,
            run,
            post_group,
            post_run,
            get_measurement_columns,
        )
        module.set_module_num(1)
        pipeline.add_module(module)
        measurements = pipeline.run(grouping={"foo": "foo-B", "bar": "bar-B"})
        assert expects[0] == "Done"

    def test_display(self):
        # Test that the individual pipeline methods do appropriate display.

        pipeline = exploding_pipeline(self)
        module = GroupModule()
        module.show_window = True
        callbacks_called = set()

        def prepare_run(workspace):
            workspace.measurements[
                nucleus.measurement.IMAGE, nucleus.measurement.GROUP_NUMBER, 1
            ] = 1
            workspace.measurements[
                nucleus.measurement.IMAGE, nucleus.measurement.GROUP_INDEX, 1
            ] = 1
            return True

        def prepare_group(workspace, grouping, *args):
            return True

        def run(workspace):
            workspace.display_data.foo = "Bar"

        def display_handler(module1, display_data, image_set_number):
            assert module1 is module
            assert display_data.foo == "Bar"
            assert image_set_number == 1
            callbacks_called.add("display_handler")

        def post_group(workspace, grouping):
            workspace.display_data.bar = "Baz"

        def post_group_display_handler(module1, display_data, image_set_number):
            assert module1 is module
            assert display_data.bar == "Baz"
            assert image_set_number == 1
            callbacks_called.add("post_group_display_handler")

        def post_run(workspace):
            workspace.display_data.baz = "Foo"

        def post_run_display_handler(workspace, module1):
            assert module1 is module
            assert workspace.display_data.baz == "Foo"
            callbacks_called.add("post_run_display_handler")

        def get_measurement_columns(pipeline):
            return [
                (
                    nucleus.measurement.IMAGE,
                    "mymeasurement",
                    nucleus.measurement.COLTYPE_INTEGER,
                )
            ]

        module.setup(
            ((), ({}, (1,))),
            prepare_run_callback=prepare_run,
            prepare_group_callback=prepare_group,
            run_callback=run,
            post_group_callback=post_group,
            post_run_callback=post_run,
        )
        module.set_module_num(1)
        pipeline.add_module(module)
        m = nucleus.measurement.Measurements()
        workspace = nucleus.workspace.Workspace(
            pipeline, module, m, None, m, nucleus.image
        )
        workspace.post_group_display_handler = post_group_display_handler
        workspace.post_run_display_handler = post_run_display_handler
        assert pipeline.prepare_run(workspace)
        pipeline.prepare_group(workspace, {}, (1,))
        pipeline.run_image_set(m, 1, None, display_handler, None)
        assert "display_handler" in callbacks_called
        pipeline.post_group(workspace, {})
        assert "post_group_display_handler" in callbacks_called
        pipeline.post_run(workspace)
        assert "post_run_display_handler" in callbacks_called

    def test_catch_operational_error(self):
        """Make sure that a pipeline can catch an operational error

        This is a regression test of IMG-277
        """
        module = MyClassForTest1101()
        module.set_module_num(1)
        pipeline = nucleus.pipeline.Pipeline()
        pipeline.add_module(module)
        should_be_true = [False]

        def callback(caller, event):
            if isinstance(event, nucleus.pipeline.RunExceptionEvent):
                should_be_true[0] = True

        pipeline.add_listener(callback)
        pipeline.run()
        assert should_be_true[0]

    # FIXME: wxPython 4 PR
    # def test_catch_prepare_run_error(self):
    #     pipeline = exploding_pipeline(self)
    #     module = GroupModule()
    #     keys = ('foo', 'bar')
    #     groupings = (({'foo': 'foo-A', 'bar': 'bar-A'}, (1, 2)),
    #                  ({'foo': 'foo-B', 'bar': 'bar-B'}, (3, 4)),
    #                  ({'foo': 'foo-C', 'bar': 'bar-C'}, (5, 6)))
    #
    #     def prepare_run(workspace):
    #         m = workspace.measurements
    #         for i in range(1, 7):
    #             m[nucleus.measurement.IMAGE, nucleus.measurement.C_PATH_NAME + "_DNA", i] = \
    #                 "/imaging/analysis"
    #             m[nucleus.measurement.IMAGE, nucleus.measurement.C_FILE_NAME + "_DNA", i] = "img%d.tif" % i
    #         workspace.pipeline.report_prepare_run_error(
    #                 module, "I am configured incorrectly")
    #         return True
    #
    #     module.setup(groupings,
    #                  prepare_run_callback=prepare_run)
    #     module.set_module_num(1)
    #     pipeline.add_module(module)
    #     workspace = nucleus.workspace.Workspace(
    #             pipeline, None, None, None, nucleus.measurement.Measurements(),
    #             nucleus.image())
    #     self.assertFalse(pipeline.prepare_run(workspace))
    #     self.assertEqual(workspace.measurements.image_set_count, 0)

    def test_img_286(self):
        """Regression test for img-286: module name in class"""
        nucleus.modules.fill_modules()
        success = True
        all_keys = list(nucleus.modules.all_modules.keys())
        all_keys.sort()
        for k in all_keys:
            v = nucleus.modules.all_modules[k]
            try:
                v.module_name
            except:
                print(("%s needs to define module_name as a class variable" % k))
                success = False
        assert success

    def test_save_pipeline(self):
        pipeline = get_empty_pipeline()
        nucleus.modules.fill_modules()
        module = nucleus.modules.instantiate_module("Align")
        module.set_module_num(1)
        pipeline.add_module(module)
        fd = six.moves.StringIO()
        pipeline.save(fd)
        fd.seek(0)

        pipeline = nucleus.pipeline.Pipeline()

        def callback(caller, event):
            assert not isinstance(event, nucleus.pipeline.LoadExceptionEvent)

        pipeline.add_listener(callback)
        pipeline.load(fd)
        assert len(pipeline.modules()) == 1
        module_out = pipeline.modules()[-1]
        for setting_in, setting_out in zip(module.settings(), module_out.settings()):
            assert setting_in.value == setting_out.value

    def test_save_measurements(self):
        pipeline = get_empty_pipeline()
        nucleus.modules.fill_modules()
        module = nucleus.modules.instantiate_module("Align")
        module.set_module_num(1)
        pipeline.add_module(module)
        measurements = nucleus.measurement.Measurements()
        my_measurement = [
            numpy.random.uniform(size=numpy.random.randint(3, 25)) for i in range(20)
        ]
        my_image_measurement = [numpy.random.uniform() for i in range(20)]
        my_experiment_measurement = numpy.random.uniform()
        measurements.add_experiment_measurement("expt", my_experiment_measurement)
        for i in range(20):
            if i > 0:
                measurements.next_image_set()
            measurements.add_measurement("Foo", "Bar", my_measurement[i])
            measurements.add_image_measurement("img", my_image_measurement[i])

        with tempfile.NamedTemporaryFile() as temporary:
            with open(temporary.name, "w") as fd:
                pipeline.save_measurements(fd.name, measurements)

                fd.seek(0)

            measurements = nucleus.measurement.load_measurements(temporary.name)

        my_measurement_out = measurements.get_all_measurements("Foo", "Bar")
        assert len(my_measurement) == len(my_measurement_out)
        for m_in, m_out in zip(my_measurement, my_measurement_out):
            assert len(m_in) == len(m_out)
            assert numpy.all(m_in == m_out)
        my_image_measurement_out = measurements.get_all_measurements("Image", "img")
        assert len(my_image_measurement) == len(my_image_measurement_out)
        for m_in, m_out in zip(my_image_measurement, my_image_measurement_out):
            assert m_in == m_out
        my_experiment_measurement_out = measurements.get_experiment_measurement("expt")
        assert (
            round(abs(my_experiment_measurement - my_experiment_measurement_out), 7)
            == 0
        )

        fd.seek(0)
        pipeline = nucleus.pipeline.Pipeline()

        def callback(caller, event):
            assert not isinstance(event, nucleus.pipeline.LoadExceptionEvent)

        pipeline.add_listener(callback)
        pipeline.load(fd)
        assert len(pipeline.modules()) == 1
        module_out = pipeline.modules()[-1]
        for setting_in, setting_out in zip(module.settings(), module_out.settings()):
            assert setting_in.value == setting_out.value

    def test_save_long_measurements(self):
        pipeline = nucleus.pipeline.Pipeline()
        nucleus.modules.fill_modules()
        module = nucleus.modules.instantiate_module("Align")
        module.set_module_num(1)
        pipeline.add_module(module)
        measurements = nucleus.measurement.Measurements()
        # m2 and m3 should go into panic mode because they differ by a cap
        m1_name = "dalkzfsrqoiualkjfrqealkjfqroupifaaalfdskquyalkhfaafdsafdsqteqteqtew"
        m2_name = "lkjxKJDSALKJDSAWQOIULKJFASOIUQELKJFAOIUQRLKFDSAOIURQLKFDSAQOIRALFAJ"
        m3_name = "druxKJDSALKJDSAWQOIULKJFASOIUQELKJFAOIUQRLKFDSAOIURQLKFDSAQOIRALFAJ"
        my_measurement = [
            numpy.random.uniform(size=numpy.random.randint(3, 25)) for i in range(20)
        ]
        my_other_measurement = [
            numpy.random.uniform(size=my_measurement[i].size) for i in range(20)
        ]
        my_final_measurement = [
            numpy.random.uniform(size=my_measurement[i].size) for i in range(20)
        ]
        measurements.add_all_measurements("Foo", m1_name, my_measurement)
        measurements.add_all_measurements("Foo", m2_name, my_other_measurement)
        measurements.add_all_measurements("Foo", m3_name, my_final_measurement)
        fd = io.StringIO()
        pipeline.save_measurements(fd, measurements)
        fd.seek(0)
        measurements = nucleus.measurement.load_measurements(fd)
        reverse_mapping = nucleus.pipeline.map_feature_names(
            [m1_name, m2_name, m3_name]
        )
        mapping = {}
        for key in list(reverse_mapping.keys()):
            mapping[reverse_mapping[key]] = key
        for name, expected in (
            (m1_name, my_measurement),
            (m2_name, my_other_measurement),
            (m3_name, my_final_measurement),
        ):
            map_name = mapping[name]
            my_measurement_out = measurements.get_all_measurements("Foo", map_name)
            for m_in, m_out in zip(expected, my_measurement_out):
                assert len(m_in) == len(m_out)
                assert numpy.all(m_in == m_out)

    # def test_pipeline_measurement(self):
    #     data = r"""CellProfiler Pipeline: http://www.nucleus.org
    #     Version:3
    #     DateRevision:20120709180131
    #     ModuleCount:1
    #     HasImagePlaneDetails:False
    #
    #     LoadImages:[module_num:1|svn_version:\'Unknown\'|variable_revision_number:11|show_window:True|notes:\x5B"Load the images by matching files in the folder against the unique text pattern for each stain\x3A \'Channel1-\' for nuclei, \'Channel2-\' for the GFP image. The two images together comprise an image set."\x5D|batch_state:array(\x5B\x5D, dtype=uint8)]
    #         File type to be loaded:individual images
    #         File selection method:Text-Exact match
    #         Number of images in each group?:3
    #         Type the text that the excluded images have in common:Do not use
    #         Analyze all subfolders within the selected folder?:None
    #         Input image file location:Elsewhere...\x7Cc\x3A\\\\trunk\\\\ExampleImages\\\\ExampleSBSImages
    #         Check image sets for unmatched or duplicate files?:Yes
    #         Group images by metadata?:No
    #         Exclude certain files?:No
    #         Specify metadata fields to group by:
    #         Select subfolders to analyze:
    #         Image count:2
    #         Text that these images have in common (case-sensitive):Channel1-01
    #         Position of this image in each group:1
    #         Extract metadata from where?:File name
    #         Regular expression that finds metadata in the file name:.*-(?P<ImageNumber>\\\\d*)-(?P<Row>.*)-(?P<Column>\\\\d*)
    #         Type the regular expression that finds metadata in the subfolder path:.*\x5B\\\\\\\\/\x5D(?P<Date>.*)\x5B\\\\\\\\/\x5D(?P<Run>.*)$
    #         Channel count:1
    #         Group the movie frames?:No
    #         Grouping method:Interleaved
    #         Number of channels per group:2
    #         Load the input as images or objects?:Images
    #         Name this loaded image:rawGFP
    #         Name this loaded object:Nuclei
    #         Retain outlines of loaded objects?:No
    #         Name the outline image:NucleiOutlines
    #         Channel number:1
    #         Rescale intensities?:Yes
    #         Text that these images have in common (case-sensitive):Channel2-01
    #         Position of this image in each group:2
    #         Extract metadata from where?:File name
    #         Regular expression that finds metadata in the file name:.*-(?P<ImageNumber>\\\\d*)-(?P<Row>.*)-(?P<Column>\\\\d*)
    #         Type the regular expression that finds metadata in the subfolder path:.*\x5B\\\\\\\\/\x5D(?P<Date>.*)\x5B\\\\\\\\/\x5D(?P<Run>.*)$
    #         Channel count:1
    #         Group the movie frames?:No
    #         Grouping method:Interleaved
    #         Number of channels per group:2
    #         Load the input as images or objects?:Images
    #         Name this loaded image:rawDNA
    #         Name this loaded object:Nuclei
    #         Retain outlines of loaded objects?:No
    #         Name the outline image:NucleiOutlines
    #         Channel number:1
    #         Rescale intensities?:Yes
    #     """
    #             maybe_download_sbs()
    #             path = os.path.join(example_images_directory(), "ExampleSBSImages")
    #             pipeline = nucleus.pipeline.Pipeline()
    #             pipeline.load(six.moves.StringIO(data))
    #             module = pipeline.modules()[0]
    #             self.assertTrue(isinstance(module, LI.LoadImages))
    #             module.location.custom_path = path
    #             m = nucleus.measurement.Measurements()
    #             image_set_list = nucleus.image()
    #             self.assertTrue(pipeline.prepare_run(nucleus.workspace.Workspace(
    #                 pipeline, module, None, None, m, image_set_list)))
    #             pipeline_text = m.get_experiment_measurement(nucleus.pipeline.M_PIPELINE)
    #             pipeline_text = pipeline_text.encode("us-ascii")
    #             pipeline = nucleus.pipeline.Pipeline()
    #             pipeline.loadtxt(six.moves.StringIO(pipeline_text))
    #             self.assertEqual(len(pipeline.modules()), 1)
    #             module_out = pipeline.modules()[0]
    #             self.assertTrue(isinstance(module_out, module.__class__))
    #             self.assertEqual(len(module_out.settings()), len(module.settings()))
    #             for m1setting, m2setting in zip(module.settings(), module_out.settings()):
    #                 self.assertTrue(isinstance(m1setting, nucleus.setting.Setting))
    #                 self.assertTrue(isinstance(m2setting, nucleus.setting.Setting))
    #                 self.assertEqual(m1setting.value, m2setting.value)

    def test_unicode_save(self):
        pipeline = get_empty_pipeline()
        module = TestModuleWithMeasurement()
        # Little endian utf-16 encoding
        module.my_variable.value = "∑"
        module.other_variable.value = "∢8"
        module.set_module_num(1)
        module.notes = "αβ"
        pipeline.add_module(module)
        fd = six.moves.StringIO()
        pipeline.savetxt(fd, save_image_plane_details=False)
        result = fd.getvalue()
        lines = result.split("\n")
        assert len(lines) == 11
        text, value = lines[-3].split(":")
        assert value == '∑'
        text, value = lines[-2].split(":")
        assert value == '∢8'
        mline = lines[7]
        idx0 = mline.find("notes:")
        mline = mline[(idx0 + 6) :]
        idx1 = mline.find("|")
        value = eval(mline[:idx1])
        assert value == module.notes

    def test_unicode_save_and_load(self):
        #
        # Put "TestModuleWithMeasurement" into the module list
        #
        nucleus.modules.fill_modules()
        nucleus.modules.all_modules[
            TestModuleWithMeasurement.module_name
        ] = TestModuleWithMeasurement
        #
        # Continue with test
        #
        pipeline = get_empty_pipeline()

        def callback(caller, event):
            assert not isinstance(event, nucleus.pipeline.LoadExceptionEvent)

        pipeline.add_listener(callback)
        module = TestModuleWithMeasurement()
        module.my_variable.value = "∑"
        module.set_module_num(1)
        module.notes = "∑"
        pipeline.add_module(module)
        fd = io.StringIO()
        pipeline.savetxt(fd)
        fd.seek(0)
        pipeline.loadtxt(fd)
        assert len(pipeline.modules()) == 1
        result_module = pipeline.modules()[0]
        assert isinstance(result_module, TestModuleWithMeasurement)
        assert module.notes == eval(result_module.notes)
        assert module.my_variable.value == result_module.my_variable.value

    def test_deprecated_unicode_load(self):
        pipeline = get_empty_pipeline()
        deprecated_pipeline_file = os.path.realpath(
            os.path.join(os.path.dirname(__file__), "../data/pipeline/v3.cppipe")
        )
        pipeline.loadtxt(deprecated_pipeline_file)
        module = TestModuleWithMeasurement()
        module.my_variable.value = "\\\\u2211"
        module.set_module_num(1)
        module.notes = "\\u03B1\\\\u03B2"
        assert len(pipeline.modules()) == 1
        result_module = pipeline.modules()[0]
        assert isinstance(result_module, TestModuleWithMeasurement)
        assert module.notes == result_module.notes
        assert module.my_variable.value == result_module.my_variable.value

    # Sorry Ray, Python 2.6 and below doesn't have @skip
    if False:

        @unittest.skip("skipping profiling AllModules - too slow")
        @numpy.testing.decorators.slow
        def test_profile_example_all(self):
            """
            Profile ExampleAllModulesPipeline

            Dependencies:
            User must have ExampleImages on their machine,
            in a location which can be found by example_images_directory().
            This directory should contain the pipeline ExampleAllModulesPipeline
            """
            example_dir = tests.modules.example_images_directory()
            if not example_dir:
                import warnings

                warnings.warn(
                    "example_images_directory not found, skipping profiling of ExampleAllModulesPipeline"
                )
                return
            pipeline_dir = os.path.join(example_dir, "ExampleAllModulesPipeline")
            pipeline_filename = os.path.join(
                pipeline_dir, "ExampleAllModulesPipeline.cp"
            )
            image_dir = os.path.join(pipeline_dir, "Images")

            # Might be better to write these paths into the pipeline
            old_image_dir = nucleus.preferences.get_default_image_directory()
            nucleus.preferences.set_default_image_directory(image_dir)
            profile_pipeline(pipeline_filename)
            nucleus.preferences.set_default_image_directory(old_image_dir)

    # def test_profile_example_fly(self):
    #     """
    #     Profile ExampleFlyImages pipeline
    #
    #     """
    #     maybe_download_fly()
    #     example_dir = example_images_directory()
    #     pipeline_dir = os.path.join(example_dir, 'ExampleFlyImages')
    #     pipeline_filename = os.path.join(pipeline_dir, 'ExampleFly.cppipe')
    #
    #     #Might be better to write these paths into the pipeline
    #     old_image_dir = cpprefs.get_default_image_directory()
    #     cpprefs.set_default_image_directory(pipeline_dir)
    #     fd = urlopen(
    #         "http://nucleus.org/ExampleFlyImages/ExampleFlyURL.cppipe")
    #     build_dir = os.path.join(
    #         os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    #         "build")
    #     if not os.path.isdir(build_dir):
    #         os.makedirs(build_dir)
    #     profile_pipeline(fd, output_filename=os.path.join(build_dir, "profile.txt"))
    #     cpprefs.set_default_image_directory(old_image_dir)

    def test_get_provider_dictionary_nothing(self):
        for module in (
            ATestModule(),
            ATestModule([nucleus.setting.Choice("foo", ["Hello", "World"])]),
        ):
            pipeline = get_empty_pipeline()
            module.set_module_num(1)
            pipeline.add_module(module)
            for groupname in (
                "imagegroup",
                "objectgroup",
                "measurementsgroup",
            ):
                d = pipeline.get_provider_dictionary(groupname)
                assert len(d) == 0

    def test_get_provider_dictionary_image(self):
        pipeline = get_empty_pipeline()
        my_setting = nucleus.setting.ImageNameProvider("foo", IMAGE_NAME)
        module = ATestModule([my_setting])
        module.set_module_num(1)
        pipeline.add_module(module)
        d = pipeline.get_provider_dictionary("imagegroup")
        assert len(d) == 1
        assert list(d.keys())[0] == IMAGE_NAME
        providers = d[IMAGE_NAME]
        assert len(providers) == 1
        provider = providers[0]
        assert provider[0] == module
        assert provider[1] == my_setting
        for group in ("objectgroup", "measurementsgroup"):
            assert len(pipeline.get_provider_dictionary(group)) == 0

    def test_get_provider_dictionary_object(self):
        pipeline = get_empty_pipeline()
        my_setting = nucleus.setting.ObjectNameProvider("foo", OBJECT_NAME)
        module = ATestModule([my_setting])
        module.set_module_num(1)
        pipeline.add_module(module)
        d = pipeline.get_provider_dictionary("objectgroup")
        assert len(d) == 1
        assert list(d.keys())[0] == OBJECT_NAME
        providers = d[OBJECT_NAME]
        assert len(providers) == 1
        provider = providers[0]
        assert provider[0] == module
        assert provider[1] == my_setting
        for group in ("imagegroup", "measurementsgroup"):
            assert len(pipeline.get_provider_dictionary(group)) == 0

    def test_get_provider_dictionary_measurement(self):
        pipeline = get_empty_pipeline()
        module = ATestModule(
            measurement_columns=[
                (OBJECT_NAME, FEATURE_NAME, nucleus.measurement.COLTYPE_FLOAT)
            ]
        )
        module.set_module_num(1)
        pipeline.add_module(module)
        d = pipeline.get_provider_dictionary("measurementsgroup")
        assert len(d) == 1
        key = list(d.keys())[0]
        assert len(key) == 2
        assert key[0] == OBJECT_NAME
        assert key[1] == FEATURE_NAME
        providers = d[key]
        assert len(providers) == 1
        provider = providers[0]
        assert provider[0] == module
        for group in ("objectgroup", "imagegroup"):
            assert len(pipeline.get_provider_dictionary(group)) == 0

    def test_get_provider_dictionary_other(self):
        pipeline = get_empty_pipeline()
        module = ATestModule(
            other_providers={"imagegroup": [IMAGE_NAME]}
        )
        module.set_module_num(1)
        pipeline.add_module(module)
        d = pipeline.get_provider_dictionary("imagegroup")
        assert len(d) == 1
        assert list(d.keys())[0] == IMAGE_NAME
        providers = d[IMAGE_NAME]
        assert len(providers) == 1
        provider = providers[0]
        assert provider[0] == module
        for group in ("objectgroup", "measurementsgroup"):
            assert len(pipeline.get_provider_dictionary(group)) == 0

    def test_get_provider_dictionary_combo(self):
        pipeline = get_empty_pipeline()
        image_setting = nucleus.setting.ImageNameProvider("foo", IMAGE_NAME)
        object_setting = nucleus.setting.ObjectNameProvider("foo", OBJECT_NAME)
        measurement_columns = [
            (OBJECT_NAME, FEATURE_NAME, nucleus.measurement.COLTYPE_FLOAT)
        ]
        other_providers = {"imagegroup": [ALT_IMAGE_NAME]}
        module = ATestModule(
            settings=[image_setting, object_setting],
            measurement_columns=measurement_columns,
            other_providers=other_providers,
        )
        module.set_module_num(1)
        pipeline.add_module(module)
        d = pipeline.get_provider_dictionary("imagegroup")
        assert len(d) == 2
        assert IMAGE_NAME in d
        providers = d[IMAGE_NAME]
        assert len(providers) == 1
        provider = providers[0]
        assert provider[0] == module
        assert provider[1] == image_setting
        assert ALT_IMAGE_NAME in d
        providers = d[ALT_IMAGE_NAME]
        assert len(providers) == 1
        provider = providers[0]
        assert len(provider) == 2
        assert provider[0] == module

        d = pipeline.get_provider_dictionary("objectgroup")
        assert len(d) == 1
        assert OBJECT_NAME in d
        providers = d[OBJECT_NAME]
        assert len(providers) == 1
        provider = providers[0]
        assert len(provider) == 2
        assert provider[0] == module
        assert provider[1] == object_setting

        d = pipeline.get_provider_dictionary("measurementsgroup")
        assert len(d) == 1
        key = list(d.keys())[0]
        assert len(key) == 2
        assert key[0] == OBJECT_NAME
        assert key[1] == FEATURE_NAME
        assert len(providers) == 1
        provider = providers[0]
        assert provider[0] == module

    def test_get_provider_module(self):
        #
        # Module 1 provides IMAGE_NAME
        # Module 2 provides OBJECT_NAME
        # Module 3 provides IMAGE_NAME again
        # Module 4 might be a consumer
        #
        # Test disambiguation of the sources
        #
        pipeline = get_empty_pipeline()
        my_image_setting_1 = nucleus.setting.ImageNameProvider("foo", IMAGE_NAME)
        my_image_setting_2 = nucleus.setting.ImageNameProvider("foo", IMAGE_NAME)
        my_object_setting = nucleus.setting.ObjectNameProvider("foo", OBJECT_NAME)
        module1 = ATestModule(settings=[my_image_setting_1])
        module2 = ATestModule(settings=[my_object_setting])
        module3 = ATestModule(settings=[my_image_setting_2])
        module4 = ATestModule()

        for i, module in enumerate((module1, module2, module3, module4)):
            module.module_num = i + 1
            pipeline.add_module(module)
        d = pipeline.get_provider_dictionary("imagegroup")
        assert len(d) == 1
        assert IMAGE_NAME in d
        assert len(d[IMAGE_NAME]) == 2
        for module in (module1, module3):
            assert any([x[0] == module for x in d[IMAGE_NAME]])

        d = pipeline.get_provider_dictionary("imagegroup", module1)
        assert len(d) == 0

        d = pipeline.get_provider_dictionary("imagegroup", module2)
        assert len(d) == 1
        assert IMAGE_NAME in d
        assert d[IMAGE_NAME][0][0] == module1

        d = pipeline.get_provider_dictionary("imagegroup", module4)
        assert len(d) == 1
        assert IMAGE_NAME in d
        assert len(d[IMAGE_NAME]) == 1
        assert d[IMAGE_NAME][0][0] == module3

    def test_get_dependency_graph_empty(self):
        for module in (
            ATestModule(),
            ATestModule([nucleus.setting.Choice("foo", ["Hello", "World"])]),
            ATestModule([nucleus.setting.ImageNameProvider("foo", IMAGE_NAME)]),
            ATestModule([nucleus.setting.ImageNameSubscriber("foo", IMAGE_NAME)]),
        ):
            pipeline = nucleus.pipeline.Pipeline()
            module.set_module_num(1)
            pipeline.add_module(module)
            result = pipeline.get_dependency_graph()
            assert len(result) == 0

    def test_get_dependency_graph_image(self):
        pipeline = nucleus.pipeline.Pipeline()
        for i, module in enumerate(
            (
                ATestModule([nucleus.setting.ImageNameProvider("foo", IMAGE_NAME)]),
                ATestModule([nucleus.setting.ImageNameProvider("foo", ALT_IMAGE_NAME)]),
                ATestModule([nucleus.setting.ImageNameSubscriber("foo", IMAGE_NAME)]),
            )
        ):
            module.module_num = i + 1
            pipeline.add_module(module)
        g = pipeline.get_dependency_graph()
        assert len(g) == 1
        edge = g[0]
        assert isinstance(edge, nucleus.pipeline.ImageDependency)
        assert edge.source == pipeline.modules()[0]
        assert edge.source_setting == pipeline.modules()[0].settings()[0]
        assert edge.image_name == IMAGE_NAME
        assert edge.destination == pipeline.modules()[2]
        assert edge.destination_setting == pipeline.modules()[2].settings()[0]

    def test_get_dependency_graph_object(self):
        pipeline = nucleus.pipeline.Pipeline()
        for i, module in enumerate(
            (
                ATestModule([nucleus.setting.ObjectNameProvider("foo", OBJECT_NAME)]),
                ATestModule([nucleus.setting.ImageNameProvider("foo", IMAGE_NAME)]),
                ATestModule([nucleus.setting.ObjectNameSubscriber("foo", OBJECT_NAME)]),
            )
        ):
            module.module_num = i + 1
            pipeline.add_module(module)
        g = pipeline.get_dependency_graph()
        assert len(g) == 1
        edge = g[0]
        assert isinstance(edge, nucleus.pipeline.ObjectDependency)
        assert edge.source == pipeline.modules()[0]
        assert edge.source_setting == pipeline.modules()[0].settings()[0]
        assert edge.object_name == OBJECT_NAME
        assert edge.destination == pipeline.modules()[2]
        assert edge.destination_setting == pipeline.modules()[2].settings()[0]

    def test_get_dependency_graph_measurement(self):
        pipeline = nucleus.pipeline.Pipeline()
        measurement_columns = [
            (OBJECT_NAME, FEATURE_NAME, nucleus.measurement.COLTYPE_FLOAT)
        ]
        measurement_setting = nucleus.setting.Measurement(
            "text", lambda: OBJECT_NAME, FEATURE_NAME
        )
        for i, module in enumerate(
            (
                ATestModule(measurement_columns=measurement_columns),
                ATestModule([nucleus.setting.ImageNameProvider("foo", ALT_IMAGE_NAME)]),
                ATestModule([measurement_setting]),
            )
        ):
            module.module_num = i + 1
            pipeline.add_module(module)
        g = pipeline.get_dependency_graph()
        assert len(g) == 1
        edge = g[0]
        assert isinstance(edge, nucleus.pipeline.MeasurementDependency)
        assert edge.source == pipeline.modules()[0]
        assert edge.object_name == OBJECT_NAME
        assert edge.feature == FEATURE_NAME
        assert edge.destination == pipeline.modules()[2]
        assert edge.destination_setting == pipeline.modules()[2].settings()[0]

    def test_read_image_plane_details(self):
        test_data = (
            (
                [],
                ['"foo","1","2","3"', '"bar","4","5","6"'],
                (("foo", 1, 2, 3, {}), ("bar", 4, 5, 6, {})),
            ),
            (
                ["Well", "Plate"],
                [
                    '"foo","1","2",,"A01","P-12345"',
                    '"bar","4",,"6",,"P-67890"',
                    '"baz","7","8",,"A03",',
                ],
                (
                    ("foo", 1, 2, None, {"Well": "A01", "Plate": "P-12345"}),
                    ("bar", 4, None, 6, {"Plate": "P-67890"}),
                    ("baz", 7, 8, None, {"Well": "A03"}),
                ),
            ),
            (
                ["Well"],
                ['"foo","1","2","3","Î±Î²"'],
                [("foo", 1, 2, 3, {"Well": "αβ"})],
            ),
            ([], [r'"\foo"bar","4","5","6"'], [(r'\foo"bar', 4, 5, 6)]),
        )

        for metadata_columns, body_lines, expected in test_data:
            s = '"%s":"%d","%s":"%d"\n' % (
                "Version",
                1,
                "PlaneCount",
                len(body_lines),
            )
            s += (
                '"'
                + '","'.join(
                    [
                        "URL",
                        "Series",
                        "Index",
                        "Channel"
                    ]
                    + metadata_columns
                )
                + '"\n'
            )

            s += "\n".join(body_lines) + "\n"

            with io.StringIO(s) as fd:
                result = nucleus.pipeline.read_file_list(fd)

            assert len(result) == len(expected)

            for r, e in zip(result, expected):
                assert r == e[0]

    def test_write_image_plane_details(self):
        test_data = ("foo", "\\u03b1\\u03b2")

        fd = six.moves.StringIO()

        nucleus.pipeline.write_file_list(fd, test_data)

        fd.seek(0)

        result = nucleus.pipeline.read_file_list(fd)

        for x, y in zip(result, test_data):
            if not isinstance(y, str):
                y = y.encode("utf-8")

            assert x == y

    def test_read_file_list_pathnames(self):
        root = os.path.split(__file__)[0]
        paths = [os.path.join(root, x) for x in ("foo.tif", "bar.tif")]
        fd = six.moves.StringIO("\n".join([paths[0], "", paths[1]]))
        p = nucleus.pipeline.Pipeline()
        p.read_file_list(fd)
        assert len(p.file_list) == 2
        for path in paths:
            assert nucleus.modules.loadimages.pathname2url(path) in p.file_list

    def test_read_file_list_urls(self):
        root = os.path.split(__file__)[0]
        file_url = nucleus.modules.loadimages.pathname2url(
            os.path.join(root, "foo.tif")
        )
        urls = [
            "http://nucleus.org/foo.tif",
            file_url,
            "https://github.com/foo.tif",
            "ftp://example.com/foo.tif",
        ]
        fd = six.moves.StringIO("\n".join(urls))
        p = nucleus.pipeline.Pipeline()
        p.read_file_list(fd)
        assert len(p.file_list) == len(urls)
        for url in urls:
            assert url in p.file_list

    def test_read_file_list_file(self):
        urls = [
            "http://nucleus.org/foo.tif",
            "https://github.com/foo.tif",
            "ftp://example.com/foo.tif",
        ]

        content = "\n".join(urls)

        with tempfile.NamedTemporaryFile() as temporary:
            with open(temporary.name, "w") as fp:
                fp.write(content)

                fp.seek(0)

            pipeline = nucleus.pipeline.Pipeline()

            pipeline.read_file_list(fp.name)

        assert len(pipeline.file_list) == len(urls)

        for url in urls:
            assert url in pipeline.file_list

    def test_read_http_file_list(self):
        url = "https://gist.githubusercontent.com/mcquin/67438dc4e8481c5b1d3881df56e1c4c4/raw/274835d9d3fef990d8bf34c4ee5f991b3880d74f/gistfile1.txt"
        urls = [
            "ftp://example.com/foo.tif",
            "http://cellprofiler.org/foo.tif",
            "https://github.com/foo.tif"
        ]
        p = nucleus.pipeline.Pipeline()
        p.read_file_list(url)
        assert len(p.file_list) == len(urls)
        for url in urls:
            assert url in p.file_list


def profile_pipeline(pipeline_filename, output_filename=None, always_run=True):
    """
    Run the provided pipeline, output the profiled results to a file.
    Pipeline is run each time by default, if canskip_rerun = True
    the pipeline is only run if the profile results filename does not exist

    Parameters
    --------------
    pipeline_filename: str
        Absolute path to pipeline
    output_filename: str, optional
        Output file for profiled results. Default is cpprefs default output directory.
    always_run: Bool, optional
        By default, only runs if output_filename does not exist
        If always_run = True, then always runs
    """

    # helper function
    def run_pipeline(
        pipeline_filename,
        image_set_start=None,
        image_set_end=None,
        groups=None,
        measurements_filename=None,
    ):
        pipeline = nucleus.pipeline.Pipeline()
        measurements = None
        pipeline.load(pipeline_filename)
        measurements = pipeline.run(
            image_set_start=image_set_start,
            image_set_end=image_set_end,
            grouping=groups,
            measurements_filename=measurements_filename,
            initial_measurements=measurements,
        )

    if not output_filename:
        pipeline_name = os.path.basename(pipeline_filename).split(".")[0]
        output_filename = os.path.join(
            nucleus.preferences.get_default_output_directory(),
            pipeline_name + "_profile",
        )

    if not os.path.exists(output_filename) or always_run:
        print(("Profiling %s" % pipeline_filename))
        cProfile.runctx(
            "run_pipeline(pipeline_filename)", globals(), locals(), output_filename
        )

    p = pstats.Stats(output_filename)
    # sort by cumulative time spent, optionally strip directory names
    to_print = p.sort_stats("cumulative")
    to_print.print_stats(20)


class ATestModule(nucleus.module.Module):
    module_name = "ATestModule"
    variable_revision_number = 1

    def __init__(self, settings=[], measurement_columns=[], other_providers={}):
        super(type(self), self).__init__()
        self.__settings = settings
        self.__measurement_columns = measurement_columns
        self.__other_providers = other_providers

    def settings(self):
        return self.__settings

    def get_measurement_columns(self, pipeline):
        return self.__measurement_columns

    def other_providers(self, group):
        if group not in list(self.__other_providers.keys()):
            return []
        return self.__other_providers[group]

    def get_categories(self, pipeline, object_name):
        categories = set()
        for cobject_name, cfeature_name, ctype in self.get_measurement_columns(
            pipeline
        ):
            if cobject_name == object_name:
                categories.add(cfeature_name.split("_")[0])
        return list(categories)

    def get_measurements(self, pipeline, object_name, category):
        measurements = set()
        for cobject_name, cfeature_name, ctype in self.get_measurement_columns(
            pipeline
        ):
            ccategory, measurement = cfeature_name.split("_", 1)
            if cobject_name == object_name and category == category:
                measurements.add(measurement)
        return list(measurements)


class TestModuleWithMeasurement(nucleus.module.Module):
    module_name = "Test0801"
    category = "Test"
    variable_revision_number = 1

    def create_settings(self):
        self.my_variable = nucleus.setting.Text("", "")
        self.other_variable = nucleus.setting.Text("", "")

    def settings(self):
        return [self.my_variable, self.other_variable]

    module_name = "TestModuleWithMeasurement"
    variable_revision_number = 1

    def module_class(self):
        return "nucleus.tests.Test_Pipeline.TestModuleWithMeasurement"

    def get_measurement_columns(self, pipeline):
        return [(nucleus.measurement.IMAGE, self.my_variable.value, "varchar(255)")]


class MyClassForTest1101(nucleus.module.Module):
    def create_settings(self):
        self.my_variable = nucleus.setting.Text("", "")

    def settings(self):
        return [self.my_variable]

    module_name = "MyClassForTest1101"
    variable_revision_number = 1

    def module_class(self):
        return "nucleus.tests.Test_Pipeline.MyClassForTest1101"

    def prepare_run(self, workspace, *args):
        image_set = workspace.image_set_list.get_image_set(0)
        workspace.measurements.add_measurement("Image", "Foo", 1)
        return True

    def prepare_group(self, workspace, *args):
        image_set = workspace.image_set_list.get_image_set(0)
        image = nucleus.image.Image(numpy.zeros((5, 5)))
        image_set.add("dummy", image)
        return True

    def run(self, *args):
        import MySQLdb

        raise MySQLdb.OperationalError("Bogus error")


class GroupModule(nucleus.module.Module):
    module_name = "Group"
    variable_revision_number = 1

    def setup(
        self,
        groupings,
        prepare_run_callback=None,
        prepare_group_callback=None,
        run_callback=None,
        post_group_callback=None,
        post_run_callback=None,
        get_measurement_columns_callback=None,
        display_callback=None,
        display_post_group_callback=None,
        display_post_run_callback=None,
    ):
        self.prepare_run_callback = prepare_run_callback
        self.prepare_group_callback = prepare_group_callback
        self.run_callback = run_callback
        self.post_group_callback = post_group_callback
        self.post_run_callback = post_run_callback
        self.groupings = groupings
        self.get_measurement_columns_callback = get_measurement_columns_callback
        self.display_callback = None
        self.display_post_group_callback = None
        self.display_post_run_callback = None

    def settings(self):
        return []

    def get_groupings(self, workspace):
        return self.groupings

    def prepare_run(self, *args):
        if self.prepare_run_callback is not None:
            return self.prepare_run_callback(*args)
        return True

    def prepare_group(self, *args):
        if self.prepare_group_callback is not None:
            return self.prepare_group_callback(*args)
        return True

    def run(self, *args):
        if self.run_callback is not None:
            return self.run_callback(*args)

    def post_run(self, *args):
        if self.post_run_callback is not None:
            return self.post_run_callback(*args)

    def post_group(self, *args):
        if self.post_group_callback is not None:
            return self.post_group_callback(*args)

    def get_measurement_columns(self, *args):
        if self.get_measurement_columns_callback is not None:
            return self.get_measurement_columns_callback(*args)
        return []

    def display(self, workspace, figure):
        if self.display_callback is not None:
            return self.display_callback(workspace, figure)
        return super(GroupModule, self).display(workspace, figure)

    def display_post_group(self, workspace, figure):
        if self.display_post_group_callback is not None:
            return self.display_post_group_callback(workspace, figure)
        return super(GroupModule, self).display_post_group(workspace, figure)

    def display_post_run(self, workspace, figure):
        if self.display_post_run is not None:
            return self.display_post_run_callback(workspace, figure)
        return super(GroupModule, self).display_post_run(workspace, figure)


class TestUtils(unittest.TestCase):
    def test_EncapsulateUnicode(self):
        a = nucleus.pipeline.encapsulate_string("Hello")
        assert a.shape == (1,)
        assert a.dtype.kind == "U"
        assert a[0] == "Hello"

    def test_EncapsulateCell(self):
        cell = numpy.ndarray((1, 1), dtype=object)
        cell[0, 0] = "Hello, world"
        nucleus.pipeline.encapsulate_strings_in_arrays(cell)
        assert isinstance(cell[0, 0], numpy.ndarray)
        assert cell[0, 0][0] == "Hello, world"

    def test_EncapsulateStruct(self):
        struct = numpy.ndarray((1, 1), dtype=[("foo", object)])
        struct["foo"][0, 0] = "Hello, world"
        nucleus.pipeline.encapsulate_strings_in_arrays(struct)
        assert isinstance(struct["foo"][0, 0], numpy.ndarray)
        assert struct["foo"][0, 0][0] == "Hello, world"

    def test_EncapsulateCellInStruct(self):
        struct = numpy.ndarray((1, 1), dtype=[("foo", object)])
        cell = numpy.ndarray((1, 1), dtype=object)
        cell[0, 0] = "Hello, world"
        struct["foo"][0, 0] = cell
        nucleus.pipeline.encapsulate_strings_in_arrays(struct)
        assert isinstance(cell[0, 0], numpy.ndarray)
        assert cell[0, 0][0] == "Hello, world"

    def test_EncapsulateStructInCell(self):
        struct = numpy.ndarray((1, 1), dtype=[("foo", object)])
        cell = numpy.ndarray((1, 1), dtype=object)
        cell[0, 0] = struct
        struct["foo"][0, 0] = "Hello, world"
        nucleus.pipeline.encapsulate_strings_in_arrays(cell)
        assert isinstance(struct["foo"][0, 0], numpy.ndarray)
        assert struct["foo"][0, 0][0] == "Hello, world"