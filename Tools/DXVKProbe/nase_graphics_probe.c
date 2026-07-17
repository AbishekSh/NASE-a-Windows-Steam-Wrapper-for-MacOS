#define WIN32_LEAN_AND_MEAN
#define VK_NO_PROTOTYPES
#include <windows.h>
#include <d3d11.h>
#include <dxgi.h>
#include <stdio.h>
#include <vulkan/vulkan.h>

static int probe_vulkan(void) {
    HMODULE module = LoadLibraryA("vulkan-1.dll");
    if (!module) {
        fprintf(stderr, "VULKAN_ERROR: could not load vulkan-1.dll (%lu)\n", GetLastError());
        return 10;
    }
    PFN_vkGetInstanceProcAddr get_instance_proc =
        (PFN_vkGetInstanceProcAddr)GetProcAddress(module, "vkGetInstanceProcAddr");
    if (!get_instance_proc) {
        fprintf(stderr, "VULKAN_ERROR: vkGetInstanceProcAddr is missing\n");
        return 11;
    }
    PFN_vkCreateInstance create_instance =
        (PFN_vkCreateInstance)get_instance_proc(VK_NULL_HANDLE, "vkCreateInstance");
    VkApplicationInfo app = {VK_STRUCTURE_TYPE_APPLICATION_INFO};
    app.pApplicationName = "NASE Graphics Probe";
    app.apiVersion = VK_API_VERSION_1_0;
    VkInstanceCreateInfo create_info = {VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
    create_info.pApplicationInfo = &app;
    VkInstance instance = VK_NULL_HANDLE;
    VkResult result = create_instance(&create_info, NULL, &instance);
    if (result != VK_SUCCESS) {
        fprintf(stderr, "VULKAN_ERROR: vkCreateInstance returned %d\n", result);
        return 12;
    }
    PFN_vkEnumeratePhysicalDevices enumerate_devices =
        (PFN_vkEnumeratePhysicalDevices)get_instance_proc(instance, "vkEnumeratePhysicalDevices");
    PFN_vkGetPhysicalDeviceProperties get_properties =
        (PFN_vkGetPhysicalDeviceProperties)get_instance_proc(instance, "vkGetPhysicalDeviceProperties");
    PFN_vkGetPhysicalDeviceQueueFamilyProperties get_queues =
        (PFN_vkGetPhysicalDeviceQueueFamilyProperties)get_instance_proc(instance, "vkGetPhysicalDeviceQueueFamilyProperties");
    PFN_vkCreateDevice create_device =
        (PFN_vkCreateDevice)get_instance_proc(instance, "vkCreateDevice");
    PFN_vkDestroyDevice destroy_device =
        (PFN_vkDestroyDevice)get_instance_proc(instance, "vkDestroyDevice");
    PFN_vkDestroyInstance destroy_instance =
        (PFN_vkDestroyInstance)get_instance_proc(instance, "vkDestroyInstance");
    uint32_t count = 0;
    result = enumerate_devices(instance, &count, NULL);
    if (result != VK_SUCCESS || count == 0) {
        fprintf(stderr, "VULKAN_ERROR: no Vulkan physical device (%d)\n", result);
        destroy_instance(instance, NULL);
        return 13;
    }
    VkPhysicalDevice physical_devices[16];
    if (count > 16) count = 16;
    result = enumerate_devices(instance, &count, physical_devices);
    VkPhysicalDeviceProperties properties;
    get_properties(physical_devices[0], &properties);
    printf("VULKAN_GPU: %s\n", properties.deviceName);
    uint32_t queue_count = 0;
    get_queues(physical_devices[0], &queue_count, NULL);
    VkQueueFamilyProperties queues[64];
    if (queue_count > 64) queue_count = 64;
    get_queues(physical_devices[0], &queue_count, queues);
    uint32_t family = UINT32_MAX;
    for (uint32_t index = 0; index < queue_count; ++index) {
        if (queues[index].queueCount && (queues[index].queueFlags & VK_QUEUE_GRAPHICS_BIT)) {
            family = index;
            break;
        }
    }
    if (family == UINT32_MAX) {
        fprintf(stderr, "VULKAN_ERROR: no graphics queue family\n");
        destroy_instance(instance, NULL);
        return 14;
    }
    float priority = 1.0f;
    VkDeviceQueueCreateInfo queue_info = {VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};
    queue_info.queueFamilyIndex = family;
    queue_info.queueCount = 1;
    queue_info.pQueuePriorities = &priority;
    VkDeviceCreateInfo device_info = {VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};
    device_info.queueCreateInfoCount = 1;
    device_info.pQueueCreateInfos = &queue_info;
    VkDevice device = VK_NULL_HANDLE;
    result = create_device(physical_devices[0], &device_info, NULL, &device);
    if (result != VK_SUCCESS) {
        fprintf(stderr, "VULKAN_ERROR: vkCreateDevice returned %d\n", result);
        destroy_instance(instance, NULL);
        return 15;
    }
    printf("VULKAN_DEVICE_CREATED: yes\n");
    destroy_device(device, NULL);
    destroy_instance(instance, NULL);
    FreeLibrary(module);
    return 0;
}

static int probe_d3d11(void) {
    ID3D11Device *device = NULL;
    ID3D11DeviceContext *context = NULL;
    D3D_FEATURE_LEVEL selected_level;
    const D3D_FEATURE_LEVEL levels[] = {
        D3D_FEATURE_LEVEL_11_0, D3D_FEATURE_LEVEL_10_1, D3D_FEATURE_LEVEL_10_0
    };
    HRESULT result = D3D11CreateDevice(
        NULL, D3D_DRIVER_TYPE_HARDWARE, NULL, 0, levels,
        sizeof(levels) / sizeof(levels[0]), D3D11_SDK_VERSION,
        &device, &selected_level, &context
    );
    if (FAILED(result)) {
        fprintf(stderr, "D3D11_ERROR: D3D11CreateDevice returned 0x%08lx\n", (unsigned long)result);
        return 20;
    }
    printf("D3D11_DEVICE_CREATED: yes\nD3D11_FEATURE_LEVEL: 0x%x\n", selected_level);
    context->lpVtbl->Release(context);
    device->lpVtbl->Release(device);
    return 0;
}

int main(void) {
    int vulkan_result = probe_vulkan();
    if (vulkan_result != 0) return vulkan_result;
    return probe_d3d11();
}
