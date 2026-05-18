#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <time.h>

#include <algorithm>
#include <cctype>
#include <iostream>
#include <string>
#include <vector>

#include <opencv2/opencv.hpp>
#include <opencv2/highgui.hpp>
#include <opencv2/videoio.hpp>

#include "yolo11.h"
#include "image_utils.h"
#include "image_drawing.h"

static volatile sig_atomic_t g_stop = 0;

static void signal_handler(int)
{
    g_stop = 1;
}

static double now_ms()
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1000000.0;
}

static void usage(const char* prog)
{
    printf("Usage:\n");
    printf("  %s <model_path> [video_device|video_file] [--no-display] [--benchmark] [--warmup N] [--max-frames N]\n", prog);
    printf("\n");
    printf("Examples:\n");
    printf("  %s model/yolo11.rknn /dev/video73\n", prog);
    printf("  %s model/yolo11.rknn 0\n", prog);
    printf("  %s model/yolo11.rknn /dev/video73 --no-display\n", prog);
    printf("  %s model/yolo11.rknn pedestrian_detection_test_video_1.flv --no-display --benchmark --warmup 30 --max-frames 300\n", prog);
    printf("\n");
    printf("Press q or ESC to quit.\n");
}

static bool is_number(const std::string& s)
{
    if (s.empty()) return false;
    for (char c : s)
    {
        if (c < '0' || c > '9') return false;
    }
    return true;
}

static image_buffer_t mat_to_image_buffer(cv::Mat& rgb)
{
    image_buffer_t img;
    memset(&img, 0, sizeof(img));
    img.width = rgb.cols;
    img.height = rgb.rows;
    img.width_stride = rgb.cols;
    img.height_stride = rgb.rows;
    img.format = IMAGE_FORMAT_RGB888;
    img.size = static_cast<int>(rgb.total() * rgb.elemSize());
    img.virt_addr = reinterpret_cast<unsigned char*>(rgb.data);
    img.fd = 0;
    return img;
}

static std::string fourcc_to_string(double fourcc_value)
{
    int fourcc = static_cast<int>(fourcc_value);
    std::string text(4, ' ');
    text[0] = static_cast<char>(fourcc & 0xFF);
    text[1] = static_cast<char>((fourcc >> 8) & 0xFF);
    text[2] = static_cast<char>((fourcc >> 16) & 0xFF);
    text[3] = static_cast<char>((fourcc >> 24) & 0xFF);
    for (char& ch : text)
    {
        if (!std::isprint(static_cast<unsigned char>(ch)))
        {
            ch = '?';
        }
    }
    return text;
}

static bool open_video_source(const std::string& video_src, cv::VideoCapture* cap)
{
    std::string camera_index_text = video_src;
    const std::string device_prefix = "/dev/video";
    if (video_src.rfind(device_prefix, 0) == 0)
    {
        camera_index_text = video_src.substr(device_prefix.size());
    }

    if (is_number(camera_index_text))
    {
        int camera_index = std::stoi(camera_index_text);
        if (cap->open(camera_index, cv::CAP_V4L2))
        {
            return true;
        }
        return cap->open(camera_index);
    }

    if (cap->open(video_src, cv::CAP_V4L2))
    {
        return true;
    }
    return cap->open(video_src);
}

static bool is_camera_source(const std::string& video_src)
{
    return is_number(video_src) || video_src.rfind("/dev/video", 0) == 0;
}

static void configure_camera_capture(cv::VideoCapture* cap)
{
    cap->set(cv::CAP_PROP_FOURCC, cv::VideoWriter::fourcc('M', 'J', 'P', 'G'));
    cap->set(cv::CAP_PROP_FRAME_WIDTH, 640);
    cap->set(cv::CAP_PROP_FRAME_HEIGHT, 480);
    cap->set(cv::CAP_PROP_FPS, 30);
    cap->set(cv::CAP_PROP_BUFFERSIZE, 1);
}

static void print_capture_info(const cv::VideoCapture& cap)
{
    double width = cap.get(cv::CAP_PROP_FRAME_WIDTH);
    double height = cap.get(cv::CAP_PROP_FRAME_HEIGHT);
    double fps = cap.get(cv::CAP_PROP_FPS);
    std::string fourcc = fourcc_to_string(cap.get(cv::CAP_PROP_FOURCC));
    std::cout << "Capture configured: "
              << width << "x" << height
              << " @" << fps << " FPS, fourcc=" << fourcc << std::endl;
}

typedef struct {
    int warmup_frames;
    int measured_frames;
    int total_frames;
    double read_ms;
    double color_ms;
    double infer_ms;
    double total_ms;
} benchmark_stats_t;

static void reset_stats(benchmark_stats_t* stats)
{
    memset(stats, 0, sizeof(*stats));
}

static void update_stats(benchmark_stats_t* stats, bool measure, double read_ms, double color_ms, double infer_ms, double total_ms)
{
    stats->total_frames++;
    if (!measure)
    {
        stats->warmup_frames++;
        return;
    }

    stats->measured_frames++;
    stats->read_ms += read_ms;
    stats->color_ms += color_ms;
    stats->infer_ms += infer_ms;
    stats->total_ms += total_ms;
}

static void print_benchmark_summary(const benchmark_stats_t& stats)
{
    printf("\nBenchmark summary:\n");
    printf("  warmup frames: %d\n", stats.warmup_frames);
    printf("  measured frames: %d\n", stats.measured_frames);
    if (stats.measured_frames <= 0)
    {
        printf("  no measured frames collected\n");
        return;
    }

    double measured = static_cast<double>(stats.measured_frames);
    double avg_read_ms = stats.read_ms / measured;
    double avg_color_ms = stats.color_ms / measured;
    double avg_infer_ms = stats.infer_ms / measured;
    double avg_total_ms = stats.total_ms / measured;
    double infer_fps = (avg_infer_ms > 0.0) ? (1000.0 / avg_infer_ms) : 0.0;
    double e2e_fps = (avg_total_ms > 0.0) ? (1000.0 / avg_total_ms) : 0.0;

    printf("  avg read/decode: %.2f ms\n", avg_read_ms);
    printf("  avg BGR->RGB: %.2f ms\n", avg_color_ms);
    printf("  avg inference: %.2f ms\n", avg_infer_ms);
    printf("  avg end-to-end: %.2f ms\n", avg_total_ms);
    printf("  model-only FPS: %.2f\n", infer_fps);
    printf("  end-to-end FPS: %.2f\n", e2e_fps);
}

static void draw_results_on_bgr(cv::Mat& frame_bgr, const object_detect_result_list& od_results)
{
    char text[256];
    for (int i = 0; i < od_results.count; ++i)
    {
        const object_detect_result* det = &od_results.results[i];
        int x1 = det->box.left;
        int y1 = det->box.top;
        int x2 = det->box.right;
        int y2 = det->box.bottom;

        x1 = std::max(0, std::min(x1, frame_bgr.cols - 1));
        y1 = std::max(0, std::min(y1, frame_bgr.rows - 1));
        x2 = std::max(0, std::min(x2, frame_bgr.cols - 1));
        y2 = std::max(0, std::min(y2, frame_bgr.rows - 1));

        cv::rectangle(frame_bgr, cv::Rect(cv::Point(x1, y1), cv::Point(x2, y2)), cv::Scalar(255, 0, 0), 2);
        snprintf(text, sizeof(text), "%s %.1f%%", coco_cls_to_name(det->cls_id), det->prop * 100.0f);

        int baseline = 0;
        cv::Size ts = cv::getTextSize(text, cv::FONT_HERSHEY_SIMPLEX, 0.55, 1, &baseline);
        int tx = x1;
        int ty = std::max(ts.height + 4, y1 - 5);
        cv::rectangle(frame_bgr,
                      cv::Point(tx, ty - ts.height - 4),
                      cv::Point(tx + ts.width + 6, ty + baseline),
                      cv::Scalar(0, 0, 255),
                      cv::FILLED);
        cv::putText(frame_bgr, text, cv::Point(tx + 3, ty - 2), cv::FONT_HERSHEY_SIMPLEX,
                    0.55, cv::Scalar(255, 255, 255), 1, cv::LINE_AA);
    }
}

int main(int argc, char** argv)
{
    if (argc < 2)
    {
        usage(argv[0]);
        return -1;
    }

    const char* model_path = argv[1];
    std::string video_src = "0";
    bool show_window = true;
    bool benchmark_mode = false;
    int warmup_frames = 0;
    int max_frames = 0;
    for (int i = 2; i < argc; ++i)
    {
        std::string arg = argv[i];
        if (arg == "--no-display")
        {
            show_window = false;
            continue;
        }
        if (arg == "--benchmark")
        {
            benchmark_mode = true;
            continue;
        }
        if (arg == "--warmup")
        {
            if (i + 1 >= argc)
            {
                usage(argv[0]);
                return -1;
            }
            warmup_frames = std::stoi(argv[++i]);
            continue;
        }
        if (arg == "--max-frames")
        {
            if (i + 1 >= argc)
            {
                usage(argv[0]);
                return -1;
            }
            max_frames = std::stoi(argv[++i]);
            continue;
        }
        video_src = arg;
    }

    if (benchmark_mode && warmup_frames == 0)
    {
        warmup_frames = 30;
    }

    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    int ret = 0;
    rknn_app_context_t app_ctx;
    memset(&app_ctx, 0, sizeof(app_ctx));

    init_post_process();

    ret = init_yolo11_model(model_path, &app_ctx);
    if (ret != 0)
    {
        printf("init_yolo11_model fail! ret=%d model_path=%s\n", ret, model_path);
        deinit_post_process();
        return -1;
    }

    cv::VideoCapture cap;
    if (!open_video_source(video_src, &cap))
    {
        std::cerr << "Failed to open camera: " << video_src << std::endl;
        release_yolo11_model(&app_ctx);
        deinit_post_process();
        return -1;
    }
    bool camera_source = is_camera_source(video_src);
    if (camera_source)
    {
        configure_camera_capture(&cap);
    }

    double fps = 0.0;
    const double alpha = 0.90;  // EMA smoothing
    benchmark_stats_t stats;
    reset_stats(&stats);

    if (show_window)
    {
        cv::namedWindow("RKNN YOLO11 Camera", cv::WINDOW_AUTOSIZE);
    }
    if (benchmark_mode)
    {
        std::cout << "Benchmark mode enabled"
                  << " | warmup=" << warmup_frames
                  << " | max_frames=" << max_frames
                  << std::endl;
    }
    print_capture_info(cap);
    std::cout << "Camera opened. Press q or ESC to quit." << std::endl;

    while (!g_stop)
    {
        cv::Mat frame_bgr;
        double t0 = now_ms();
        if (!cap.read(frame_bgr) || frame_bgr.empty())
        {
            std::cerr << "Failed to read frame." << std::endl;
            break;
        }
        double t1 = now_ms();

        cv::Mat frame_rgb;
        cv::cvtColor(frame_bgr, frame_rgb, cv::COLOR_BGR2RGB);
        image_buffer_t src_image = mat_to_image_buffer(frame_rgb);

        object_detect_result_list od_results;
        memset(&od_results, 0, sizeof(od_results));

        double t2 = now_ms();
        ret = inference_yolo11_model(&app_ctx, &src_image, &od_results);
        double t3 = now_ms();
        if (ret != 0)
        {
            std::cerr << "inference_yolo11_model failed: ret=" << ret << std::endl;
            break;
        }

        double t4 = now_ms();

        double total_ms = t4 - t0;
        double inst_fps = (total_ms > 0.0) ? (1000.0 / total_ms) : 0.0;
        fps = (fps <= 0.0) ? inst_fps : (alpha * fps + (1.0 - alpha) * inst_fps);
        bool measure = !benchmark_mode || stats.total_frames >= warmup_frames;
        update_stats(&stats, measure, t1 - t0, t2 - t1, t3 - t2, total_ms);

        if (show_window)
        {
            draw_results_on_bgr(frame_bgr, od_results);

            char perf[256];
            snprintf(perf, sizeof(perf),
                     "FPS %.1f | cap %.1f ms | inf %.1f ms | draw %.1f ms | det %d",
                     fps, t1 - t0, t3 - t2, t4 - t3, od_results.count);
            cv::putText(frame_bgr, perf, cv::Point(10, 28), cv::FONT_HERSHEY_SIMPLEX,
                        0.7, cv::Scalar(0, 255, 0), 2, cv::LINE_AA);

            cv::imshow("RKNN YOLO11 Camera", frame_bgr);
            int key = cv::waitKey(1) & 0xFF;
            if (key == 'q' || key == 27)
            {
                break;
            }
        }

        if (max_frames > 0 && stats.total_frames >= max_frames)
        {
            break;
        }
    }

    cap.release();
    if (show_window)
    {
        cv::destroyAllWindows();
    }
    deinit_post_process();

    ret = release_yolo11_model(&app_ctx);
    if (ret != 0)
    {
        printf("release_yolo11_model fail! ret=%d\n", ret);
    }

    if (benchmark_mode)
    {
        print_benchmark_summary(stats);
    }

    return 0;
}
