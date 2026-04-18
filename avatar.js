// avatar.js

// Global references for other scripts
window.avatarState = 'idle'; // 'idle', 'speaking', 'thinking'
window.mariaMixer = null;

document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('avatar-container');
    if (!container) return;

    // 1. Scene Setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#121212'); // Dark theme background
    // scene.fog = new THREE.Fog('#121212', 2, 10);

    const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 100);
    camera.position.set(0, 1.2, 3); // Positioned to look at upper body typically

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.outputEncoding = THREE.sRGBEncoding;
    container.appendChild(renderer.domElement);

    // 2. Lighting
    const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444444, 0.6);
    hemiLight.position.set(0, 20, 0);
    scene.add(hemiLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(2, 10, 5);
    scene.add(dirLight);

    const fillLight = new THREE.DirectionalLight(0x90b0d0, 0.4); // Subtle cool fill
    fillLight.position.set(-2, 2, -2);
    scene.add(fillLight);

    // 3. Load Model
    let mariaModel = null;
    const loader = new THREE.GLTFLoader();
    
    loader.load('3d female ai assistant.glb', (gltf) => {
        mariaModel = gltf.scene;
        
        // Center and scale the model dynamically based on its bounding box
        const box = new THREE.Box3().setFromObject(mariaModel);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z);
        
        // Normalize size
        const scale = 2.0 / maxDim;
        mariaModel.scale.setScalar(scale);

        // Adjust position so the head/chest is near center
        box.setFromObject(mariaModel);
        const newCenter = box.getCenter(new THREE.Vector3());
        mariaModel.position.x -= newCenter.x;
        mariaModel.position.y -= newCenter.y - 0.5; // push model down slightly so head is in view
        mariaModel.position.z -= newCenter.z;
        
        scene.add(mariaModel);

        // Handle native animations if they exist
        if (gltf.animations && gltf.animations.length > 0) {
            window.mariaMixer = new THREE.AnimationMixer(mariaModel);
            const action = window.mariaMixer.clipAction(gltf.animations[0]);
            action.play();
        }

    }, undefined, (error) => {
        console.error("Error loading 3D Avatar:", error);
    });

    // 4. Animation Loop & Procedural States
    const clock = new THREE.Clock();
    let time = 0;
    
    // Model base rotation adjustment (face forward)
    const baseRotationY = -Math.PI / 2.2; // ~81 degrees turn towards camera

    function animate() {
        requestAnimationFrame(animate);
        const delta = clock.getDelta();
        time += delta;

        if (window.mariaMixer) {
            window.mariaMixer.update(delta);
        }

        if (mariaModel) {
            // Procedural animation blending based on state
            let targetRotY = baseRotationY;
            let targetPosY = mariaModel.userData.baseY || mariaModel.position.y;
            
            // Track base position if not tracked
            if (mariaModel.userData.baseY === undefined) {
                mariaModel.userData.baseY = mariaModel.position.y;
            }

            if (window.avatarState === 'thinking') {
                targetRotY = baseRotationY + Math.sin(time * 1.5) * 0.05;
                mariaModel.position.y = targetPosY + Math.sin(time * 2) * 0.005;
            } else if (window.avatarState === 'speaking') {
                targetRotY = baseRotationY + Math.sin(time * 0.5) * 0.03;
                mariaModel.position.y = targetPosY + Math.abs(Math.sin(time * 10)) * 0.01;
            } else {
                targetRotY = baseRotationY;
                mariaModel.position.y = targetPosY + Math.sin(time * 1.5) * 0.01;
            }

            // Smoothly interpolate rotation
            mariaModel.rotation.y += (targetRotY - mariaModel.rotation.y) * 0.05;
        }

        renderer.render(scene, camera);

    }

    animate();

    // 5. Handling Resizes
    window.addEventListener('resize', () => {
        if (!container) return;
        camera.aspect = container.clientWidth / container.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(container.clientWidth, container.clientHeight);
    });
});
