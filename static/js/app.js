// Main JavaScript
console.log('SkillUp Agent loaded');

function loadTrendingSkills() {
    console.log('Loading trending skills...');
}

function submitSkill() {
    const skill = document.getElementById('skillInput').value;
    console.log('Skill submitted:', skill);
}

function uploadResume() {
    const file = document.getElementById('resumeFile').files[0];
    if (!file) {
        console.error('No resume file selected');
        return;
    }

    const formData = new FormData();
    formData.append('resume', file);

    fetch('/api/analyze-resume', {
        method: 'POST',
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            console.log('Resume analysis result:', data);
        })
        .catch(error => {
            console.error('Resume upload failed:', error);
        });
}
